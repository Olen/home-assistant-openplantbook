"""Tests for the upload run record and the upload entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from openplantbook_sdk.sdk import RateLimitError

from custom_components.openplantbook.const import FLOW_UPLOAD_DATA
from custom_components.openplantbook.upload_health import (
    STATUS_DISABLED,
    STATUS_FAILED,
    STATUS_NOTHING_NEW,
    STATUS_RATE_LIMITED,
    STATUS_UPLOADED,
    classify_run,
)
from custom_components.openplantbook.uploader import plant_data_upload

from .conftest import TEST_CLIENT_ID, run
from .ha_common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

STATUS_SENSOR = "sensor.openplantbook_upload_status"
LAST_UPLOAD_SENSOR = "sensor.openplantbook_last_upload"
PROBLEM_SENSOR = "binary_sensor.openplantbook_upload_problem"

MONDAY = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)


class TestClassifyRun:
    """How a finished run is classified."""

    def test_accepted_upload(self) -> None:
        assert (
            classify_run(plants_total=2, plants_failed=0, sent=True, accepted=True)
            == STATUS_UPLOADED
        )

    def test_rejected_upload(self) -> None:
        assert (
            classify_run(plants_total=2, plants_failed=0, sent=True, accepted=False)
            == STATUS_FAILED
        )

    def test_no_plant_could_be_registered(self) -> None:
        assert (
            classify_run(plants_total=3, plants_failed=3, sent=False, accepted=False)
            == STATUS_FAILED
        )

    def test_some_plants_registered_but_nothing_new(self) -> None:
        assert (
            classify_run(plants_total=3, plants_failed=1, sent=False, accepted=False)
            == STATUS_NOTHING_NEW
        )

    def test_no_plants_at_all(self) -> None:
        assert (
            classify_run(plants_total=0, plants_failed=0, sent=False, accepted=False)
            == STATUS_NOTHING_NEW
        )


def problem(hass: HomeAssistant) -> State:
    return hass.states.get(PROBLEM_SENSOR)


class TestUploadRecordsFailures:
    """plant_data_upload announces runs that end in an exception."""

    async def test_rate_limit_keeps_earlier_registration_failures(
        self, hass: HomeAssistant, uploading: MockConfigEntry
    ) -> None:
        async def fail_one_then_rate_limit(hass, entry, call, tally):
            tally.failed_plants["fern-device"] = "Fern"
            tally.errors.append("invalid pid")
            raise RateLimitError("slow down")

        with (
            patch(
                "custom_components.openplantbook.uploader._plant_data_upload",
                side_effect=fail_one_then_rate_limit,
            ),
            pytest.raises(RateLimitError),
        ):
            await plant_data_upload(hass, uploading)
        await hass.async_block_till_done()

        status = hass.states.get(STATUS_SENSOR)
        assert status.state == STATUS_RATE_LIMITED
        assert status.attributes["failed_plants"] == ["Fern"]
        assert (
            status.attributes["error"]
            == "invalid pid; OpenPlantbook API rate limit exceeded"
        )

    async def test_unexpected_error_is_a_failed_run(
        self, hass: HomeAssistant, uploading: MockConfigEntry
    ) -> None:
        with (
            patch(
                "custom_components.openplantbook.uploader._plant_data_upload",
                side_effect=RuntimeError("api down"),
            ),
            pytest.raises(RuntimeError),
        ):
            await plant_data_upload(hass, uploading)
        await hass.async_block_till_done()

        assert hass.states.get(STATUS_SENSOR).state == STATUS_FAILED
        assert problem(hass).attributes["error"] == "api down"

    async def test_upload_service_records_nothing_new(
        self, hass: HomeAssistant, uploading: MockConfigEntry
    ) -> None:
        await hass.services.async_call(
            "openplantbook", "upload", {}, blocking=True, return_response=True
        )
        await hass.async_block_till_done()
        assert hass.states.get(STATUS_SENSOR).state == STATUS_NOTHING_NEW


class TestUploadSensors:
    """The status and last-upload sensors."""

    async def test_uploading_off(
        self, hass: HomeAssistant, init_integration: MockConfigEntry
    ) -> None:
        assert hass.states.get(STATUS_SENSOR).state == STATUS_DISABLED
        assert problem(hass).state == STATE_UNAVAILABLE

    async def test_sensors_follow_a_run(
        self, hass: HomeAssistant, uploading: MockConfigEntry
    ) -> None:
        await run(
            hass,
            STATUS_FAILED,
            cloud_latest=MONDAY,
            failed_plants={"fern-device": "Fern"},
            error="token expired",
        )
        status = hass.states.get(STATUS_SENSOR)
        assert status.state == STATUS_FAILED
        assert status.attributes["failed_plants"] == ["Fern"]
        assert status.attributes["error"] == "token expired"
        assert hass.states.get(LAST_UPLOAD_SENSOR).state == MONDAY.isoformat()


class TestUploadProblem:
    """When the upload problem sensor is on, and why."""

    async def test_a_failed_run_is_a_problem_until_data_gets_through(
        self, hass: HomeAssistant, uploading: MockConfigEntry
    ) -> None:
        await run(hass, STATUS_UPLOADED)
        assert problem(hass).state == STATE_OFF
        await run(hass, STATUS_FAILED)
        assert problem(hass).attributes["reason"] == STATUS_FAILED
        await run(hass, STATUS_UPLOADED)
        assert problem(hass).state == STATE_OFF

    async def test_no_data_for_three_days_is_overdue(
        self, hass: HomeAssistant, uploading: MockConfigEntry, freezer
    ) -> None:
        await run(hass, STATUS_UPLOADED)
        freezer.tick(timedelta(days=2))
        await run(hass, STATUS_NOTHING_NEW)
        assert problem(hass).state == STATE_OFF

        freezer.tick(timedelta(days=1, minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert problem(hass).state == STATE_ON
        assert problem(hass).attributes["reason"] == "overdue"

        await run(hass, STATUS_UPLOADED)
        assert problem(hass).state == STATE_OFF

    async def test_a_plant_failure_lasts_until_that_plant_registers(
        self, hass: HomeAssistant, uploading: MockConfigEntry
    ) -> None:
        await run(
            hass,
            STATUS_UPLOADED,
            failed_plants={"fern-1": "Fern"},
            registered_plants={"basil"},
        )
        assert problem(hass).attributes["reason"] == "plants_failed"
        assert problem(hass).attributes["failed_plants"] == ["Fern"]

        # Skipped (no species yet), and another plant with the same name works.
        await run(hass, STATUS_UPLOADED, registered_plants={"basil", "fern-2"})
        assert problem(hass).state == STATE_ON

        await run(hass, STATUS_UPLOADED, registered_plants={"basil", "fern-1"})
        assert problem(hass).state == STATE_OFF

    async def test_turning_uploads_back_on_starts_a_fresh_window(
        self, hass: HomeAssistant, uploading: MockConfigEntry, freezer
    ) -> None:
        await run(hass, STATUS_UPLOADED)
        hass.config_entries.async_update_entry(
            uploading, options={FLOW_UPLOAD_DATA: False}
        )
        await hass.async_block_till_done()
        assert problem(hass).state == STATE_UNAVAILABLE

        freezer.tick(timedelta(days=10))
        hass.config_entries.async_update_entry(
            uploading, options={FLOW_UPLOAD_DATA: True}
        )
        await hass.async_block_till_done()
        assert problem(hass).state == STATE_OFF


class TestAccounts:
    """The upload entities belong to the entry, and to its current account."""

    async def test_a_run_for_another_account_is_ignored(
        self, hass: HomeAssistant, uploading: MockConfigEntry
    ) -> None:
        await run(hass, STATUS_UPLOADED)
        # An upload that was still running when the entry got another account.
        await run(hass, STATUS_FAILED, account="previous-account")
        assert hass.states.get(STATUS_SENSOR).state == STATUS_UPLOADED
        assert problem(hass).state == STATE_OFF

    async def test_entities_are_tied_to_the_entry_not_the_account(
        self, hass: HomeAssistant, uploading: MockConfigEntry
    ) -> None:
        entry = er.async_get(hass).async_get(PROBLEM_SENSOR)
        assert entry.unique_id == f"{uploading.entry_id}_upload_problem"


class TestRestore:
    """The entities restore their own state after a restart."""

    def _saved(self, account: str) -> list:
        return [
            (
                State(STATUS_SENSOR, STATUS_FAILED),
                {"status": STATUS_FAILED, "error": "token expired", "account": account},
            ),
            (
                State(LAST_UPLOAD_SENSOR, MONDAY.isoformat()),
                {"last_upload": MONDAY.isoformat(), "account": account},
            ),
            (
                State(PROBLEM_SENSOR, STATE_ON),
                {
                    "status": STATUS_FAILED,
                    "last_upload": MONDAY.isoformat(),
                    "failed_plants": {"fern-1": "Fern"},
                    "account": account,
                },
            ),
        ]

    async def test_state_survives_a_restart(
        self, hass: HomeAssistant, mock_config_entry, mock_openplantbook_api, freezer
    ) -> None:
        freezer.move_to(MONDAY + timedelta(days=1))
        mock_restore_cache_with_extra_data(hass, self._saved(TEST_CLIENT_ID))
        mock_config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry, options={FLOW_UPLOAD_DATA: True}
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(STATUS_SENSOR).state == STATUS_FAILED
        assert hass.states.get(LAST_UPLOAD_SENSOR).state == MONDAY.isoformat()
        assert problem(hass).state == STATE_ON
        assert problem(hass).attributes["failed_plants"] == ["Fern"]

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    async def test_state_of_another_account_is_not_restored(
        self, hass: HomeAssistant, mock_config_entry, mock_openplantbook_api
    ) -> None:
        mock_restore_cache_with_extra_data(hass, self._saved("someone-else"))
        mock_config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry, options={FLOW_UPLOAD_DATA: True}
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(LAST_UPLOAD_SENSOR).state == "unknown"
        assert problem(hass).state == STATE_OFF

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
