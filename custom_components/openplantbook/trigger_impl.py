"""The upload problem triggers. Imported lazily by trigger.py, on HA 2026.7+.

They are the "Upload problem" binary sensor turning on and off, so the sensor's
state is all the memory they need: it survives restarts and reloads, and goes
unavailable - which these triggers ignore - while uploading is off.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_FOR,
    CONF_OPTIONS,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerConfig,
    make_entity_target_state_trigger,
)

from .const import DOMAIN

PROBLEM_KEY = "upload_problem"
# The entity id the sensor gets when it is first created.
DEFAULT_PROBLEM_ENTITY_ID = f"{BINARY_SENSOR_DOMAIN}.openplantbook_{PROBLEM_KEY}"

_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default=dict): vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period}
        )
    }
)


def problem_entity_id(hass: HomeAssistant) -> str:
    """The upload problem sensor's entity id, following a rename."""
    for entry in er.async_get(hass).entities.values():
        if (
            entry.platform == DOMAIN
            and entry.domain == BINARY_SENSOR_DOMAIN
            and entry.unique_id.endswith(f"_{PROBLEM_KEY}")
        ):
            return entry.entity_id
    return DEFAULT_PROBLEM_ENTITY_ID


def _problem_trigger(to_state: str) -> type[Trigger]:
    """A trigger for the upload problem sensor changing to `to_state`."""
    base = make_entity_target_state_trigger(BINARY_SENSOR_DOMAIN, to_state)

    class UploadProblemTrigger(base):
        _schema = _SCHEMA

        def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
            super().__init__(
                hass,
                TriggerConfig(
                    key=config.key,
                    target={ATTR_ENTITY_ID: [problem_entity_id(hass)]},
                    options=config.options,
                ),
            )

    return UploadProblemTrigger


def build_triggers() -> dict[str, type[Trigger]]:
    """The openplantbook.* triggers."""
    return {
        "upload_problem_started": _problem_trigger(STATE_ON),
        "upload_problem_cleared": _problem_trigger(STATE_OFF),
    }
