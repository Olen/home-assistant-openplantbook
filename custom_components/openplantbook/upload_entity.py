"""Shared base for the upload entities on the OpenPlantbook service device."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import (
    ExtraStoredData,
    RestoredExtraData,
    RestoreEntity,
)

from .const import DOMAIN, FLOW_UPLOAD_DATA
from .upload_health import SIGNAL_UPLOAD_RUN, SIGNAL_UPLOAD_SCHEDULE, UploadRun

# Saved with the restore data, so state saved for one account is never
# restored for another that ends up with the same entity ids.
ATTR_ACCOUNT = "account"


class UploadEntity(RestoreEntity):
    """Diagnostic, push-updated, and restoring its own state after a restart."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str) -> None:
        self._entry = entry
        self._account: str = entry.data[CONF_CLIENT_ID]
        self._attr_translation_key = key
        # The entry id stays the same when the entry is reconfigured for
        # another account, so these entities (and automations on them) do too.
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="OpenPlantbook",
            manufacturer="OpenPlantbook",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open.plantbook.io",
        )

    @property
    def upload_enabled(self) -> bool:
        """Whether the daily upload is turned on."""
        return bool(self._entry.options.get(FLOW_UPLOAD_DATA))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        extra = await self.async_get_last_extra_data()
        saved = extra.as_dict() if extra is not None else {}
        if saved.get(ATTR_ACCOUNT) == self._account:
            self.restore(saved)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPLOAD_RUN, self._on_run)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPLOAD_SCHEDULE, self._on_schedule
            )
        )

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        return RestoredExtraData({**self.saved_data(), ATTR_ACCOUNT: self._account})

    @callback
    def _on_run(self, run: UploadRun) -> None:
        if run.account != self._account:
            return
        self.apply_run(run)
        self.async_write_ha_state()

    @callback
    def _on_schedule(self) -> None:
        self.async_write_ha_state()

    def restore(self, saved: dict[str, Any]) -> None:
        """Take back what saved_data stored before the restart."""
        raise NotImplementedError

    def saved_data(self) -> dict[str, Any]:
        """What to keep over a restart."""
        raise NotImplementedError

    def apply_run(self, run: UploadRun) -> None:
        """Update from a finished upload run."""
        raise NotImplementedError
