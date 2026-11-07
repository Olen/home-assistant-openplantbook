"""Tests for the openplantbook.upload_problem_* triggers (HA 2026.7+)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from custom_components.openplantbook.trigger import _has_purpose_trigger_api

if not _has_purpose_trigger_api():
    pytest.skip("purpose-trigger API not available on this HA", allow_module_level=True)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.openplantbook.const import FLOW_UPLOAD_DATA
from custom_components.openplantbook.trigger import async_get_triggers
from custom_components.openplantbook.upload_health import (
    STATUS_FAILED,
    STATUS_UPLOADED,
)

from .conftest import run
from .ha_common import MockConfigEntry, async_capture_events
from .test_upload_health import PROBLEM_SENSOR

BLUEPRINTS = (
    Path(__file__).parent.parent / "blueprints" / "automation" / "openplantbook"
)


async def _automations(hass: HomeAssistant, *triggers: str) -> list[list]:
    """One automation per trigger, each firing an event named after it."""
    captured = [async_capture_events(hass, trigger) for trigger in triggers]
    # conftest strips integration dependencies, so automation's trace is not
    # set up by itself.
    assert await async_setup_component(hass, "trace", {})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "trigger": {"trigger": f"openplantbook.{trigger}"},
                    "action": {
                        "event": trigger,
                        "event_data": {
                            "reason": "{{ trigger.to_state.attributes.reason }}"
                        },
                    },
                }
                for trigger in triggers
            ]
        },
    )
    await hass.async_block_till_done()
    return captured


async def test_both_triggers_are_offered(hass: HomeAssistant) -> None:
    assert set(await async_get_triggers(hass)) == {
        "upload_problem_started",
        "upload_problem_cleared",
    }


async def test_a_problem_starts_once_and_clears_once(
    hass: HomeAssistant, uploading: MockConfigEntry
) -> None:
    await run(hass, STATUS_UPLOADED)
    started, cleared = await _automations(
        hass, "upload_problem_started", "upload_problem_cleared"
    )
    await run(hass, STATUS_FAILED)
    await run(hass, STATUS_FAILED, failed_plants={"fern": "Fern"})
    assert [e.data["reason"] for e in started] == [STATUS_FAILED]
    assert cleared == []

    await run(hass, STATUS_UPLOADED, registered_plants={"fern"})
    assert len(cleared) == 1


async def test_turning_uploads_off_and_on_fires_nothing(
    hass: HomeAssistant, uploading: MockConfigEntry
) -> None:
    await run(hass, STATUS_FAILED)
    started, cleared = await _automations(
        hass, "upload_problem_started", "upload_problem_cleared"
    )
    for enabled in (False, True):
        hass.config_entries.async_update_entry(
            uploading, options={FLOW_UPLOAD_DATA: enabled}
        )
        await hass.async_block_till_done()
    assert started == []
    assert cleared == []


async def test_the_trigger_follows_a_renamed_sensor(
    hass: HomeAssistant, uploading: MockConfigEntry
) -> None:
    er.async_get(hass).async_update_entity(
        PROBLEM_SENSOR, new_entity_id="binary_sensor.plantbook_trouble"
    )
    await hass.async_block_till_done()
    await run(hass, STATUS_UPLOADED)
    (started,) = await _automations(hass, "upload_problem_started")
    await run(hass, STATUS_FAILED)
    assert len(started) == 1


@pytest.fixture
def installed_blueprints(hass: HomeAssistant):
    """Copy the blueprints to where Home Assistant looks for them."""
    target = Path(hass.config.path("blueprints", "automation", "openplantbook"))
    shutil.copytree(BLUEPRINTS, target, dirs_exist_ok=True)
    yield
    shutil.rmtree(target)


async def test_upload_problem_blueprint(
    hass: HomeAssistant, uploading: MockConfigEntry, installed_blueprints
) -> None:
    await run(hass, STATUS_UPLOADED)
    problems = async_capture_events(hass, "problem")
    cleared = async_capture_events(hass, "cleared")
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
                                    "reason": "{{ reason }}",
                                    "error": "{{ error }}",
                                    "plants": "{{ failed_plants }}",
                                },
                            }
                        ],
                        "cleared_actions": [
                            {
                                "event": "cleared",
                                "event_data": {"reason": "{{ reason }}"},
                            }
                        ],
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()

    await run(
        hass,
        STATUS_FAILED,
        error="token expired",
        failed_plants={"fern": "Fern", "basil": "Basil"},
    )
    assert [e.data for e in problems] == [
        {"reason": STATUS_FAILED, "error": "token expired", "plants": "Basil, Fern"}
    ]

    await run(hass, STATUS_UPLOADED, registered_plants={"fern", "basil"})
    assert [e.data for e in cleared] == [{"reason": ""}]
