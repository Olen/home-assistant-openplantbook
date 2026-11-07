"""Tests for recording upload outcomes and the two upload sensors."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant, State
from openplantbook_sdk.sdk import RateLimitError

from custom_components.openplantbook.const import FLOW_UPLOAD_DATA
from custom_components.openplantbook.upload_health import (
    STATUS_DISABLED,
    STATUS_FAILED,
    STATUS_NOTHING_NEW,
    STATUS_RATE_LIMITED,
    STATUS_UPLOADED,
    claim_upload_health,
    classify_run,
    get_upload_health,
    record_enabled,
    record_run,
)
from custom_components.openplantbook.uploader import plant_data_upload

from .conftest import TEST_CLIENT_ID
from .ha_common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

STATUS_SENSOR = "sensor.openplantbook_upload_status"
LAST_UPLOAD_SENSOR = "sensor.openplantbook_last_upload"

MONDAY = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
TUESDAY = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)


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


class TestRecordRun:
    """What a recorded run keeps."""

    async def test_last_upload_is_the_newest_known_time(
        self, hass: HomeAssistant
    ) -> None:
        record_run(
            hass, status=STATUS_NOTHING_NEW, finished=TUESDAY, cloud_latest=MONDAY
        )
        assert get_upload_health(hass).last_upload == MONDAY

        record_run(hass, status=STATUS_UPLOADED, finished=TUESDAY)
        health = get_upload_health(hass)
        assert health.last_upload == TUESDAY
        assert health.previous_last_upload == MONDAY
        assert health.previous_status == STATUS_NOTHING_NEW

    async def test_a_failed_run_keeps_the_last_upload(
        self, hass: HomeAssistant
    ) -> None:
        record_run(hass, status=STATUS_UPLOADED, finished=MONDAY)
        record_run(
            hass,
            status=STATUS_FAILED,
            finished=TUESDAY,
            failed_plants=["Fern"],
            error="boom",
        )
        health = get_upload_health(hass)
        assert health.last_upload == MONDAY
        assert health.failed_plants == ["Fern"]
        assert health.error == "boom"


class TestOwnership:
    """The record belongs to one config entry."""

    async def test_a_reload_of_the_same_entry_keeps_the_history(
        self, hass: HomeAssistant
    ) -> None:
        claim_upload_health(hass, "entry-a", "account-1")
        record_run(hass, status=STATUS_UPLOADED, finished=MONDAY)
        claim_upload_health(hass, "entry-a", "account-1")
        assert get_upload_health(hass).last_upload == MONDAY

    async def test_a_new_entry_starts_fresh(self, hass: HomeAssistant) -> None:
        claim_upload_health(hass, "entry-a", "account-1")
        record_run(hass, status=STATUS_FAILED, finished=MONDAY)
        claim_upload_health(hass, "entry-b", "account-1")
        health = get_upload_health(hass)
        assert health.last_run is None
        assert health.in_outage is False

    async def test_another_account_on_the_same_entry_starts_fresh(
        self, hass: HomeAssistant
    ) -> None:
        claim_upload_health(hass, "entry-a", "account-1")
        record_run(hass, status=STATUS_UPLOADED, finished=MONDAY)
        claim_upload_health(hass, "entry-a", "account-2")
        assert get_upload_health(hass).last_upload is None

    async def test_newly_failed_plants_are_only_the_new_ones(
        self, hass: HomeAssistant
    ) -> None:
        record_run(
            hass, status=STATUS_UPLOADED, finished=MONDAY, failed_plants=["Fern"]
        )
        assert get_upload_health(hass).newly_failed_plants == ["Fern"]
        record_run(
            hass, status=STATUS_UPLOADED, finished=TUESDAY, failed_plants=["Fern"]
        )
        assert get_upload_health(hass).newly_failed_plants == []
        record_run(
            hass,
            status=STATUS_UPLOADED,
            finished=TUESDAY,
            failed_plants=["Fern", "Basil"],
        )
        assert get_upload_health(hass).newly_failed_plants == ["Basil"]

    async def test_a_manual_run_keeps_the_schedule_disabled(
        self, hass: HomeAssistant
    ) -> None:
        record_enabled(hass, False)
        record_run(hass, status=STATUS_NOTHING_NEW, finished=MONDAY)
        health = get_upload_health(hass)
        assert health.upload_enabled is False
        assert health.status == STATUS_NOTHING_NEW


class TestUploadRecordsFailures:
    """plant_data_upload records runs that end in an exception."""

    async def test_rate_limit_is_recorded_and_raised(self, hass: HomeAssistant) -> None:
        with (
            patch(
                "custom_components.openplantbook.uploader._plant_data_upload",
                side_effect=RateLimitError("slow down"),
            ),
            pytest.raises(RateLimitError),
        ):
            await plant_data_upload(hass, MagicMock())
        assert get_upload_health(hass).status == STATUS_RATE_LIMITED

    async def test_unexpected_error_is_recorded_and_raised(
        self, hass: HomeAssistant
    ) -> None:
        with (
            patch(
                "custom_components.openplantbook.uploader._plant_data_upload",
                side_effect=RuntimeError("api down"),
            ),
            pytest.raises(RuntimeError),
        ):
            await plant_data_upload(hass, MagicMock())
        health = get_upload_health(hass)
        assert health.status == STATUS_FAILED
        assert health.error == "api down"


class TestRunErrorsAreKept:
    """What failed earlier in a run survives a later exception."""

    async def test_rate_limit_keeps_earlier_registration_failures(
        self, hass: HomeAssistant
    ) -> None:
        async def fail_one_then_rate_limit(hass, entry, call, tally):
            tally.failed_plants.append("Fern")
            tally.errors.append("invalid pid")
            raise RateLimitError("slow down")

        with (
            patch(
                "custom_components.openplantbook.uploader._plant_data_upload",
                side_effect=fail_one_then_rate_limit,
            ),
            pytest.raises(RateLimitError),
        ):
            await plant_data_upload(hass, MagicMock())
        health = get_upload_health(hass)
        assert health.failed_plants == ["Fern"]
        assert health.error == "invalid pid; OpenPlantbook API rate limit exceeded"

    async def test_registration_errors_are_the_error_of_a_failed_run(
        self, hass: HomeAssistant
    ) -> None:
        async def every_plant_fails(hass, entry, call, tally):
            tally.plants_total = 2
            tally.failed_plants.extend(["Fern", "Basil"])
            tally.errors.extend(["token expired", "token expired"])

        with patch(
            "custom_components.openplantbook.uploader._plant_data_upload",
            side_effect=every_plant_fails,
        ):
            await plant_data_upload(hass, MagicMock())
        health = get_upload_health(hass)
        assert health.status == STATUS_FAILED
        assert health.error == "token expired"


class TestUploadSensors:
    """The diagnostic sensors follow the recorded runs."""

    async def test_disabled_upload_shows_disabled(
        self, hass: HomeAssistant, init_integration: MockConfigEntry
    ) -> None:
        assert hass.states.get(STATUS_SENSOR).state == STATUS_DISABLED
        assert hass.states.get(LAST_UPLOAD_SENSOR).state == "unknown"

    async def test_sensors_follow_a_run(
        self, hass: HomeAssistant, init_integration: MockConfigEntry
    ) -> None:
        record_run(
            hass,
            status=STATUS_FAILED,
            finished=TUESDAY,
            cloud_latest=MONDAY,
            failed_plants=["Fern"],
            error="token expired",
        )
        await hass.async_block_till_done()

        status = hass.states.get(STATUS_SENSOR)
        assert status.state == STATUS_FAILED
        assert status.attributes["failed_plants"] == ["Fern"]
        assert status.attributes["error"] == "token expired"
        assert hass.states.get(LAST_UPLOAD_SENSOR).state == MONDAY.isoformat()

    async def test_upload_service_records_nothing_new(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        mock_config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry, options={FLOW_UPLOAD_DATA: True}
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "openplantbook", "upload", {}, blocking=True, return_response=True
        )
        await hass.async_block_till_done()
        assert hass.states.get(STATUS_SENSOR).state == STATUS_NOTHING_NEW

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    async def test_status_and_last_upload_survive_a_restart(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        # One call: each mock_restore_cache* replaces the whole cache.
        mock_restore_cache_with_extra_data(
            hass,
            [
                (
                    State(
                        STATUS_SENSOR,
                        STATUS_FAILED,
                        {
                            "last_run": TUESDAY.isoformat(),
                            "failed_plants": ["Fern"],
                            "error": "token expired",
                        },
                    ),
                    {"in_outage": True, "account": TEST_CLIENT_ID},
                ),
                (
                    State(LAST_UPLOAD_SENSOR, MONDAY.isoformat()),
                    {"last_upload": MONDAY.isoformat(), "account": TEST_CLIENT_ID},
                ),
            ],
        )
        mock_config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry, options={FLOW_UPLOAD_DATA: True}
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        status = hass.states.get(STATUS_SENSOR)
        assert status.state == STATUS_FAILED
        assert status.attributes["failed_plants"] == ["Fern"]
        assert status.attributes["error"] == "token expired"
        assert get_upload_health(hass).last_run == TUESDAY
        assert get_upload_health(hass).in_outage is True
        assert hass.states.get(LAST_UPLOAD_SENSOR).state == MONDAY.isoformat()
        assert get_upload_health(hass).last_upload == MONDAY

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_saved_state_of_another_account_is_not_restored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openplantbook_api: MagicMock,
) -> None:
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(STATUS_SENSOR, STATUS_FAILED, {"error": "old account"}),
                {"in_outage": True, "account": "someone-else"},
            ),
            (
                State(LAST_UPLOAD_SENSOR, MONDAY.isoformat()),
                {"last_upload": MONDAY.isoformat(), "account": "someone-else"},
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={FLOW_UPLOAD_DATA: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    health = get_upload_health(hass)
    assert health.last_upload is None
    assert health.in_outage is False
    assert health.error is None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_unloading_keeps_history_but_stops_monitoring(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    record_run(hass, status=STATUS_UPLOADED, finished=MONDAY)
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    health = get_upload_health(hass)
    assert health.upload_enabled is None
    assert health.last_upload == MONDAY


async def test_removing_the_entry_forgets_the_history(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    record_run(hass, status=STATUS_UPLOADED, finished=MONDAY)
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    health = get_upload_health(hass)
    assert health.last_upload is None
    assert health.upload_enabled is None
