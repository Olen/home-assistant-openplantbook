"""Diagnostic sensors for the plant-sensor upload to OpenPlantbook."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, EntityCategory
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

# Saved with the restore data, so a state saved for one account is never
# restored for another that reuses the entity ids.
ATTR_ACCOUNT = "account"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the upload sensors."""
    async_add_entities([UploadStatusSensor(entry), LastUploadSensor(entry)])


class _UploadSensor(SensorEntity, RestoreEntity):
    """Common setup: one OpenPlantbook service device, diagnostic, push-updated."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str) -> None:
        self._account: str = entry.data[CONF_CLIENT_ID]
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
        saved = await self._async_saved_data()
        if saved is not None:
            await self._async_restore(saved)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPLOAD_HEALTH, self._on_upload_health
            )
        )
        self._update_from_health()

    async def _async_saved_data(self) -> dict[str, Any] | None:
        """The data saved before the restart, if it belongs to this account."""
        extra = await self.async_get_last_extra_data()
        if extra is None:
            return None
        saved = extra.as_dict()
        if saved.get(ATTR_ACCOUNT) != self._account:
            return None
        return saved

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        data = self._data_to_save()
        data[ATTR_ACCOUNT] = self._account
        return RestoredExtraData(data)

    async def _async_restore(self, saved: dict[str, Any]) -> None:
        raise NotImplementedError

    def _data_to_save(self) -> dict[str, Any]:
        raise NotImplementedError

    @callback
    def _on_upload_health(self, _update: str) -> None:
        self._update_from_health()
        self.async_write_ha_state()

    @callback
    def _update_from_health(self) -> None:
        raise NotImplementedError


class UploadStatusSensor(_UploadSensor):
    """How the latest upload run went."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = UPLOAD_STATUSES

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "upload_status")
        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def _async_restore(self, saved: dict[str, Any]) -> None:
        last = await self.async_get_last_state()
        if last is None or last.state not in UPLOAD_STATUSES:
            return
        last_run = last.attributes.get("last_run")
        record_restored(
            self.hass,
            status=last.state,
            # Attributes are stored as JSON, so a datetime comes back as text.
            last_run=dt_util.parse_datetime(last_run) if last_run else None,
            failed_plants=last.attributes.get("failed_plants"),
            error=last.attributes.get("error"),
            in_outage=saved.get("in_outage"),
        )

    def _data_to_save(self) -> dict[str, Any]:
        # The outage flag is not visible in the status alone.
        return {"in_outage": get_upload_health(self.hass).in_outage}

    @callback
    def _update_from_health(self) -> None:
        health = get_upload_health(self.hass)
        self._attr_native_value = health.status
        self._attr_extra_state_attributes = {
            "last_run": health.last_run,
            "failed_plants": health.failed_plants,
            "error": health.error,
        }


class LastUploadSensor(_UploadSensor):
    """When OpenPlantbook last received data: from this run or the cloud's record."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "last_upload")

    async def _async_restore(self, saved: dict[str, Any]) -> None:
        last_upload = saved.get("last_upload")
        if last_upload:
            record_restored(self.hass, last_upload=dt_util.parse_datetime(last_upload))

    def _data_to_save(self) -> dict[str, Any]:
        last_upload = get_upload_health(self.hass).last_upload
        return {"last_upload": last_upload.isoformat() if last_upload else None}

    @callback
    def _update_from_health(self) -> None:
        self._attr_native_value = get_upload_health(self.hass).last_upload
