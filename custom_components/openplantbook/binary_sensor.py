"""The "Upload problem" binary sensor: on while uploads to OpenPlantbook need attention."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .upload_entity import UploadEntity
from .upload_health import (
    FAILING_STATUSES,
    OVERDUE_AFTER,
    UploadRun,
    newest,
)

REASON_FAILED = "failed"
REASON_RATE_LIMITED = "rate_limited"
REASON_OVERDUE = "overdue"
REASON_PLANTS_FAILED = "plants_failed"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the upload problem sensor."""
    async_add_entities([UploadProblemSensor(entry)])


def _parse(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


def _text(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class UploadProblemSensor(UploadEntity, BinarySensorEntity):
    """On when the last run failed, no data arrived for a while, or plants fail.

    Unavailable while the daily upload is off, so turning it off or on is
    never mistaken for a problem starting or ending.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "upload_problem")
        self._status: str | None = None
        self._last_upload: datetime | None = None
        # When the daily upload was last turned on; the overdue clock starts
        # no earlier, so a long pause does not count as an overdue upload.
        self._watching_since: datetime = dt_util.utcnow()
        self._was_enabled: bool = self.upload_enabled
        # Plant device id -> name, for plants whose registration failed and
        # has not succeeded since. A run that skips a plant changes nothing.
        self._failed_plants: dict[str, str] = {}
        self._error: str | None = None
        self._overdue_timer: CALLBACK_TYPE | None = None

    @property
    def available(self) -> bool:
        return self.upload_enabled

    @property
    def overdue_at(self) -> datetime:
        """When no new data makes uploads overdue."""
        last = newest(self._last_upload, self._watching_since)
        return last + OVERDUE_AFTER

    @property
    def reason(self) -> str | None:
        """Why there is a problem, the most serious first; None when there is none."""
        if self._status in FAILING_STATUSES:
            return self._status
        if dt_util.utcnow() >= self.overdue_at:
            return REASON_OVERDUE
        if self._failed_plants:
            return REASON_PLANTS_FAILED
        return None

    @property
    def is_on(self) -> bool:
        return self.reason is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "failed_plants": sorted(self._failed_plants.values()),
            "last_upload": self._last_upload,
            "error": self._error,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._schedule_overdue_check()
        self.async_on_remove(self._cancel_overdue_check)

    def apply_run(self, run: UploadRun) -> None:
        self._status = run.status
        self._last_upload = newest(self._last_upload, run.cloud_latest, run.uploaded_at)
        self._error = run.error
        for device_id in run.registered_plants:
            self._failed_plants.pop(device_id, None)
        self._failed_plants.update(run.failed_plants)
        self._schedule_overdue_check()

    def saved_data(self) -> dict[str, Any]:
        return {
            "status": self._status,
            "last_upload": _text(self._last_upload),
            "watching_since": _text(self._watching_since),
            "failed_plants": self._failed_plants,
            "error": self._error,
        }

    def restore(self, saved: dict[str, Any]) -> None:
        self._status = saved.get("status")
        self._last_upload = _parse(saved.get("last_upload"))
        self._watching_since = (
            _parse(saved.get("watching_since")) or self._watching_since
        )
        self._failed_plants = dict(saved.get("failed_plants") or {})
        self._error = saved.get("error")

    @callback
    def _on_schedule(self) -> None:
        if self.upload_enabled and not self._was_enabled:
            self._watching_since = dt_util.utcnow()
            self._schedule_overdue_check()
        self._was_enabled = self.upload_enabled
        self.async_write_ha_state()

    @callback
    def _schedule_overdue_check(self) -> None:
        """Re-check when uploads become overdue, as no event marks that moment."""
        self._cancel_overdue_check()
        if dt_util.utcnow() < self.overdue_at:
            self._overdue_timer = async_track_point_in_utc_time(
                self.hass, self._on_overdue, self.overdue_at
            )

    @callback
    def _cancel_overdue_check(self) -> None:
        if self._overdue_timer is not None:
            self._overdue_timer()
            self._overdue_timer = None

    @callback
    def _on_overdue(self, _now: datetime) -> None:
        self._overdue_timer = None
        self.async_write_ha_state()
