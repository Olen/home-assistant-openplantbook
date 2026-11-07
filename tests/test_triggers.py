"""Tests for the openplantbook.upload_* triggers (HA 2026.7+)."""

from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from custom_components.openplantbook.trigger import _has_purpose_trigger_api

if not _has_purpose_trigger_api():
    pytest.skip("purpose-trigger API not available on this HA", allow_module_level=True)

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.openplantbook.trigger import async_get_triggers
from custom_components.openplantbook.upload_health import (
    STATUS_FAILED,
    STATUS_NOTHING_NEW,
    STATUS_RATE_LIMITED,
    STATUS_UPLOADED,
    record_restored,
    record_run,
)

from .ha_common import async_capture_events, async_fire_time_changed


async def _automation(hass: HomeAssistant, trigger: dict, event: str) -> list:
    events = async_capture_events(hass, event)
    # conftest strips integration dependencies, so automation's trace is not
    # set up by itself.
    assert await async_setup_component(hass, "trace", {})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": trigger,
                "action": {
                    "event": event,
                    "event_data": {
                        "status": "{{ trigger.status }}",
                        "error": "{{ trigger.error }}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()
    return events


async def _run(hass: HomeAssistant, status: str, **kwargs) -> None:
    record_run(hass, status=status, finished=dt_util.utcnow(), **kwargs)
    await hass.async_block_till_done()


async def _turn_off_automations(hass: HomeAssistant) -> None:
    """Detach the triggers, so their timers do not outlive the test."""
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "all"}, blocking=True
    )
    await hass.async_block_till_done()


async def test_all_triggers_are_offered(hass: HomeAssistant) -> None:
    assert set(await async_get_triggers(hass)) == {
        "upload_failed",
        "upload_overdue",
        "upload_recovered",
    }


async def test_upload_failed_fires_once_per_outage(hass: HomeAssistant) -> None:
    events = await _automation(
        hass, {"trigger": "openplantbook.upload_failed"}, "failed"
    )
    await _run(hass, STATUS_UPLOADED)
    await _run(hass, STATUS_FAILED, error="token expired")
    await _run(hass, STATUS_RATE_LIMITED)
    assert [e.data for e in events] == [
        {"status": STATUS_FAILED, "error": "token expired"}
    ]

    await _run(hass, STATUS_UPLOADED)
    await _run(hass, STATUS_RATE_LIMITED)
    assert len(events) == 2


async def test_upload_overdue_fires_after_the_window(
    hass: HomeAssistant, freezer
) -> None:
    await _run(hass, STATUS_UPLOADED)
    events = await _automation(
        hass,
        {"trigger": "openplantbook.upload_overdue", "options": {"for": {"days": 3}}},
        "overdue",
    )
    freezer.tick(timedelta(days=2))
    async_fire_time_changed(hass)
    await _run(hass, STATUS_NOTHING_NEW)
    assert len(events) == 0

    freezer.tick(timedelta(days=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(events) == 1

    # A later run that still sends nothing does not fire again.
    await _run(hass, STATUS_NOTHING_NEW)
    assert len(events) == 1


async def test_a_new_upload_rearms_the_overdue_window(
    hass: HomeAssistant, freezer
) -> None:
    await _run(hass, STATUS_UPLOADED)
    events = await _automation(
        hass,
        {"trigger": "openplantbook.upload_overdue", "options": {"for": {"days": 3}}},
        "overdue",
    )
    freezer.tick(timedelta(days=2))
    async_fire_time_changed(hass)
    await _run(hass, STATUS_UPLOADED)

    freezer.tick(timedelta(days=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(events) == 0
    await _turn_off_automations(hass)


async def test_overdue_at_start_waits_one_more_window(
    hass: HomeAssistant, freezer
) -> None:
    """A restart during an outage does not fire at once, but does not forget it."""
    events = await _automation(
        hass,
        {"trigger": "openplantbook.upload_overdue", "options": {"for": {"days": 3}}},
        "overdue",
    )
    record_restored(hass, last_upload=dt_util.utcnow() - timedelta(days=10))
    await hass.async_block_till_done()
    assert len(events) == 0

    freezer.tick(timedelta(days=3, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_upload_recovered_after_a_failure(hass: HomeAssistant) -> None:
    events = await _automation(
        hass,
        {"trigger": "openplantbook.upload_recovered"},
        "recovered",
    )
    await _run(hass, STATUS_UPLOADED)
    assert len(events) == 0
    await _run(hass, STATUS_FAILED)
    await _run(hass, STATUS_UPLOADED)
    assert [e.data["status"] for e in events] == [STATUS_UPLOADED]


async def test_upload_recovered_after_a_long_gap(hass: HomeAssistant, freezer) -> None:
    events = await _automation(
        hass,
        {
            "trigger": "openplantbook.upload_recovered",
            "options": {"for": {"days": 3}},
        },
        "recovered",
    )
    await _run(hass, STATUS_UPLOADED)
    freezer.tick(timedelta(days=1))
    await _run(hass, STATUS_UPLOADED)
    assert len(events) == 0

    freezer.tick(timedelta(days=5))
    await _run(hass, STATUS_NOTHING_NEW)
    await _run(hass, STATUS_UPLOADED)
    assert len(events) == 1


BLUEPRINTS = (
    Path(__file__).parent.parent / "blueprints" / "automation" / "openplantbook"
)


@pytest.fixture
def installed_blueprints(hass: HomeAssistant):
    """Copy the blueprints to where Home Assistant looks for them."""
    target = Path(hass.config.path("blueprints", "automation", "openplantbook"))
    shutil.copytree(BLUEPRINTS, target, dirs_exist_ok=True)
    yield
    shutil.rmtree(target)


async def test_upload_problem_blueprint(
    hass: HomeAssistant, installed_blueprints
) -> None:
    problems = async_capture_events(hass, "problem")
    recovered = async_capture_events(hass, "recovered")
    assert await async_setup_component(hass, "trace", {})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "openplantbook/upload_problem.yaml",
                    "input": {
                        "problem_actions": [
                            {
                                "event": "problem",
                                "event_data": {
                                    "problem": "{{ problem }}",
                                    "error": "{{ error }}",
                                    "plants": "{{ failed_plants }}",
                                    "last_upload": "{{ last_upload }}",
                                },
                            }
                        ],
                        "recovered_actions": [
                            {
                                "event": "recovered",
                                "event_data": {"problem": "{{ problem }}"},
                            }
                        ],
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()

    await _run(
        hass, STATUS_FAILED, error="token expired", failed_plants=["Fern", "Basil"]
    )
    assert [e.data for e in problems] == [
        {
            "problem": STATUS_FAILED,
            "error": "token expired",
            "plants": "Fern, Basil",
            "last_upload": "never",
        }
    ]

    await _run(hass, STATUS_UPLOADED)
    assert [e.data for e in recovered] == [{"problem": STATUS_UPLOADED}]
    await _turn_off_automations(hass)
