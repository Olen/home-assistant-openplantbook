"""Entities for the OpenPlantBook integration.

Thin Entity subclasses that replace the legacy state-only pseudo-entities
(set via hass.states.async_set). They are added through an EntityComponent for
the integration's own `openplantbook` domain, so they keep the exact same
entity_ids and attributes as before while gaining unique_ids.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, OPB_ATTR_SEARCH_RESULT, OPB_DISPLAY_PID, OPB_PID


class OpenPlantbookSearchResult(Entity):
    """Persistent entity holding the latest search results.

    State = number of results; attributes = {pid: display_pid}. Replaces the
    legacy `openplantbook.search_result` pseudo-state.
    """

    _attr_should_poll = False
    # Leave the name unset so HA does not inject a `friendly_name` attribute.
    # Consumers (e.g. examples/GUI.md's search dropdown) iterate the attribute
    # dict as a {pid: display_pid} mapping, so an extra key would corrupt it.
    _attr_name = None
    _attr_has_entity_name = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the search-result entity."""
        self.entity_id = f"{DOMAIN}.{OPB_ATTR_SEARCH_RESULT}"
        # Prefer the config entry's unique_id (the client_id) so the entity
        # unique_id stays stable if the entry is removed and re-added for the
        # same account; fall back to entry_id only when it is unset.
        self._attr_unique_id = (
            f"{entry.unique_id or entry.entry_id}_{OPB_ATTR_SEARCH_RESULT}"
        )
        self._count: int = 0
        self._results: dict[str, str] = {}

    @property
    def state(self) -> int:
        """Return the number of search results."""
        return self._count

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the {pid: display_pid} mapping of the latest search."""
        return self._results

    @callback
    def async_update_results(self, count: int, results: dict[str, str]) -> None:
        """Store the latest search results and write the new state."""
        self._count = count
        self._results = results
        self.async_write_ha_state()


class OpenPlantbookSpecies(Entity):
    """Per-species entity mirroring one cached OpenPlantbook detail result.

    State = display_pid; attributes = the full plant_data dict. Replaces the
    legacy `openplantbook.<pid>` pseudo-state. Created on fetch, removed when
    the cache entry expires.
    """

    _attr_should_poll = False
    _attr_name = None
    _attr_has_entity_name = False

    def __init__(
        self, entry: ConfigEntry, entity_id: str, plant_data: dict[str, Any]
    ) -> None:
        """Initialize a species entity with its first fetched data."""
        self.entity_id = entity_id
        # See OpenPlantbookSearchResult: prefer the stable client_id prefix.
        self._attr_unique_id = (
            f"{entry.unique_id or entry.entry_id}_{plant_data[OPB_PID]}"
        )
        self._plant_data: dict[str, Any] = plant_data

    @property
    def state(self) -> str | None:
        """Return the display_pid as the entity state."""
        return self._plant_data.get(OPB_DISPLAY_PID)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full plant_data dict as attributes."""
        return self._plant_data

    @callback
    def async_update_data(self, plant_data: dict[str, Any]) -> None:
        """Refresh the cached plant_data and write the new state."""
        self._plant_data = plant_data
        self.async_write_ha_state()
