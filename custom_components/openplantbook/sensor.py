"""Diagnostic sensors for the plant-sensor upload to OpenPlantbook."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import (
    ExtraStoredData,
    RestoredExtraData,
    RestoreEntity,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .upload_health import (
    SIGNAL_UPLOAD_HEALTH,
    UPLOAD_STATUSES,
    get_upload_health,
    record_restored,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the upload sensors."""
    async_add_entities([UploadStatusSensor(entry), LastUploadSensor(entry)])


class _UploadSensor(SensorEntity):
    """Common setup: one OpenPlantbook service device, diagnostic, push-updated."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str) -> None:
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="OpenPlantbook",
            manufacturer="OpenPlantbook",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open.plantbook.io",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Restore before listening, so our own restore signal is not handled here.
        await self._async_restore()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPLOAD_HEALTH, self._on_upload_health
            )
        )
        self._update_from_health()

    async def _async_restore(self) -> None:
        raise NotImplementedError

    @callback
    def _on_upload_health(self, _update: str) -> None:
        self._update_from_health()
        self.async_write_ha_state()

    @callback
    def _update_from_health(self) -> None:
        raise NotImplementedError


class UploadStatusSensor(_UploadSensor, RestoreEntity):
    """How the latest upload run went."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = UPLOAD_STATUSES

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "upload_status")
        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def _async_restore(self) -> None:
        last = await self.async_get_last_state()
        if last is None or last.state not in UPLOAD_STATUSES:
            return
        last_run = last.attributes.get("last_run")
        extra = await self.async_get_last_extra_data()
        record_restored(
            self.hass,
            status=last.state,
            # Attributes are stored as JSON, so a datetime comes back as text.
            last_run=dt_util.parse_datetime(last_run) if last_run else None,
            failed_plants=last.attributes.get("failed_plants"),
            error=last.attributes.get("error"),
            in_outage=extra.as_dict().get("in_outage") if extra else None,
        )

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Save the outage flag, which the status alone does not show."""
        return RestoredExtraData({"in_outage": get_upload_health(self.hass).in_outage})

    @callback
    def _update_from_health(self) -> None:
        health = get_upload_health(self.hass)
        self._attr_native_value = health.status
        self._attr_extra_state_attributes = {
            "last_run": health.last_run,
            "failed_plants": health.failed_plants,
            "error": health.error,
        }


class LastUploadSensor(_UploadSensor, RestoreSensor):
    """When OpenPlantbook last received data: from this run or the cloud's record."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "last_upload")

    async def _async_restore(self) -> None:
        last = await self.async_get_last_sensor_data()
        if last is not None and isinstance(last.native_value, datetime):
            record_restored(self.hass, last_upload=last.native_value)

    @callback
    def _update_from_health(self) -> None:
        self._attr_native_value = get_upload_health(self.hass).last_upload
