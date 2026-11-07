"""The upload-health triggers. Imported lazily by trigger.py, on HA 2026.7+."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.const import CONF_FOR, CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .upload_health import (
    SIGNAL_UPLOAD_HEALTH,
    STATUS_DISABLED,
    STATUS_UPLOADED,
    UPDATE_RESTORED,
    UPDATE_RUN,
    UploadHealth,
    get_upload_health,
)

DEFAULT_OVERDUE_FOR = timedelta(days=3)

_NO_OPTIONS_SCHEMA = vol.Schema(
    {vol.Optional(CONF_OPTIONS, default=dict): vol.Schema({})}
)
_FOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default=dict): vol.Schema(
            {
                vol.Optional(
                    CONF_FOR, default=DEFAULT_OVERDUE_FOR
                ): cv.positive_time_period
            }
        )
    }
)


def _payload(health: UploadHealth) -> dict[str, Any]:
    """Trigger variables shared by all upload triggers."""
    return {
        "status": health.status,
        "last_upload": health.last_upload,
        "error": health.error,
        "failed_plants": list(health.failed_plants),
    }


class UploadFailedTrigger(Trigger):
    """An upload run failed, outside an outage that is already going on."""

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        return _NO_OPTIONS_SCHEMA(config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        super().__init__(hass, config)

    async def async_attach_runner(
        self, run_action: TriggerActionRunner, did_not_trigger: Any | None = None
    ) -> CALLBACK_TYPE:
        @callback
        def _on_update(update: str) -> None:
            if update != UPDATE_RUN:
                return
            health = get_upload_health(self._hass)
            if health.outage_started:
                run_action(_payload(health), f"upload {health.status}")

        return async_dispatcher_connect(self._hass, SIGNAL_UPLOAD_HEALTH, _on_update)


class UploadOverdueTrigger(Trigger):
    """No data has reached OpenPlantbook for longer than `for`.

    Already overdue when the trigger is attached (a restart during an outage),
    it waits one more `for` before firing, rather than firing on every restart.
    Nothing is overdue while uploading is turned off, and turning it back on
    starts a fresh window.
    """

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        return _FOR_SCHEMA(config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        super().__init__(hass, config)
        self._duration: timedelta = (config.options or {}).get(
            CONF_FOR, DEFAULT_OVERDUE_FOR
        )

    async def async_attach_runner(
        self, run_action: TriggerActionRunner, did_not_trigger: Any | None = None
    ) -> CALLBACK_TYPE:
        attached = dt_util.utcnow()
        overdue = False
        not_before = attached
        timer: CALLBACK_TYPE | None = None

        def _deadline(health: UploadHealth) -> datetime:
            # Never seen an upload: count from when we started watching.
            last = health.last_upload or attached
            return max(last + self._duration, not_before)

        @callback
        def _evaluate(_now: datetime | None = None) -> None:
            nonlocal overdue, timer
            timer = None
            health = get_upload_health(self._hass)
            if health.status == STATUS_DISABLED:
                overdue = False
                return
            deadline = _deadline(health)
            if dt_util.utcnow() >= deadline:
                if not overdue:
                    overdue = True
                    run_action(_payload(health), "upload overdue")
                return
            overdue = False
            timer = async_track_point_in_utc_time(self._hass, _evaluate, deadline)

        @callback
        def _hold_off_if_overdue() -> None:
            """Give a value that is already overdue one more window."""
            nonlocal not_before
            health = get_upload_health(self._hass)
            if not overdue and dt_util.utcnow() >= _deadline(health):
                not_before = dt_util.utcnow() + self._duration

        @callback
        def _on_update(update: str) -> None:
            nonlocal not_before
            health = get_upload_health(self._hass)
            if update == UPDATE_RESTORED:
                _hold_off_if_overdue()
            elif health.previous_status == STATUS_DISABLED:
                not_before = dt_util.utcnow() + self._duration
            if timer is not None:
                timer()
            _evaluate()

        _hold_off_if_overdue()
        _evaluate()
        unsub = async_dispatcher_connect(self._hass, SIGNAL_UPLOAD_HEALTH, _on_update)

        @callback
        def _remove() -> None:
            unsub()
            if timer is not None:
                timer()

        return _remove


class UploadRecoveredTrigger(Trigger):
    """Data reached OpenPlantbook again after an outage or a gap longer than `for`."""

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        return _FOR_SCHEMA(config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        super().__init__(hass, config)
        self._duration: timedelta = (config.options or {}).get(
            CONF_FOR, DEFAULT_OVERDUE_FOR
        )

    async def async_attach_runner(
        self, run_action: TriggerActionRunner, did_not_trigger: Any | None = None
    ) -> CALLBACK_TYPE:
        attached = dt_util.utcnow()

        @callback
        def _on_update(update: str) -> None:
            if update != UPDATE_RUN:
                return
            health = get_upload_health(self._hass)
            if health.status != STATUS_UPLOADED:
                return
            # Never seen an upload before: count from when we started watching,
            # as the overdue trigger does.
            previous = health.previous_last_upload or attached
            was_overdue = health.last_run - previous > self._duration
            if health.outage_ended or was_overdue:
                run_action(_payload(health), "upload recovered")

        return async_dispatcher_connect(self._hass, SIGNAL_UPLOAD_HEALTH, _on_update)


def build_triggers() -> dict[str, type[Trigger]]:
    """The openplantbook.* triggers."""
    return {
        "upload_failed": UploadFailedTrigger,
        "upload_overdue": UploadOverdueTrigger,
        "upload_recovered": UploadRecoveredTrigger,
    }
