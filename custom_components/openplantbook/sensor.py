"""Diagnostic sensors for the plant-sensor upload to OpenPlantbook."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .upload_entity import UploadEntity
from .upload_health import STATUS_DISABLED, UPLOAD_STATUSES, UploadRun, newest


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the upload sensors."""
    async_add_entities([UploadStatusSensor(entry), LastUploadSensor(entry)])


def _parse(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


def _text(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class UploadStatusSensor(UploadEntity, SensorEntity):
    """How the latest upload run went, or "disabled" while uploading is off."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = UPLOAD_STATUSES

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "upload_status")
        self._status: str | None = None
        self._last_run: datetime | None = None
        self._failed_plants: list[str] = []
        self._error: str | None = None

    @property
    def native_value(self) -> str | None:
        return self._status if self.upload_enabled else STATUS_DISABLED

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "last_run": self._last_run,
            "failed_plants": self._failed_plants,
            "error": self._error,
        }

    def apply_run(self, run: UploadRun) -> None:
        self._status = run.status
        self._last_run = run.finished
        self._failed_plants = sorted(run.failed_plants.values())
        self._error = run.error

    def saved_data(self) -> dict[str, Any]:
        return {
            "status": self._status,
            "last_run": _text(self._last_run),
            "failed_plants": self._failed_plants,
            "error": self._error,
        }

    def restore(self, saved: dict[str, Any]) -> None:
        if saved.get("status") in UPLOAD_STATUSES:
            self._status = saved["status"]
        self._last_run = _parse(saved.get("last_run"))
        self._failed_plants = list(saved.get("failed_plants") or [])
        self._error = saved.get("error")


class LastUploadSensor(UploadEntity, SensorEntity):
    """When OpenPlantbook last received data: from a run or the cloud's record."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "last_upload")
        self._last_upload: datetime | None = None

    @property
    def native_value(self) -> datetime | None:
        return self._last_upload

    def apply_run(self, run: UploadRun) -> None:
        self._last_upload = newest(self._last_upload, run.cloud_latest, run.uploaded_at)

    def saved_data(self) -> dict[str, Any]:
        return {"last_upload": _text(self._last_upload)}

    def restore(self, saved: dict[str, Any]) -> None:
        self._last_upload = _parse(saved.get("last_upload"))
