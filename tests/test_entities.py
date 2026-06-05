"""Tests for the real OpenPlantbook entities and their unique_ids."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook.const import (
    ATTR_HOURS,
    DOMAIN,
    OPB_SERVICE_CLEAN_CACHE,
    OPB_SERVICE_GET,
)


async def test_search_result_entity_has_unique_id(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """The search_result entity is registered with a client_id-based unique_id."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(f"{DOMAIN}.search_result")
    assert entry is not None
    # unique_id is prefixed with the config entry's unique_id (the client_id),
    # which the conftest entry backfills to "test_client_id".
    assert entry.unique_id == "test_client_id_search_result"


async def test_search_result_survives_reload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_openplantbook_api,
) -> None:
    """After a config-entry reload, search_result is re-registered with the same unique_id."""
    ent_reg = er.async_get(hass)
    before = ent_reg.async_get(f"{DOMAIN}.search_result")
    assert before is not None

    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    after = ent_reg.async_get(f"{DOMAIN}.search_result")
    assert after is not None
    assert after.unique_id == before.unique_id
    assert hass.states.get(f"{DOMAIN}.search_result") is not None


async def test_species_entity_has_unique_id(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_openplantbook_api,
) -> None:
    """A fetched species entity is registered with a client_id-based unique_id."""
    await hass.services.async_call(
        DOMAIN, OPB_SERVICE_GET, {"species": "monstera deliciosa"}, blocking=True
    )
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("openplantbook.monstera_deliciosa")
    assert entry is not None
    # Prefixed with the config entry's unique_id (client_id), suffixed with pid.
    assert entry.unique_id == "test_client_id_monstera deliciosa"


async def test_species_registry_entry_purged_on_cache_clean(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_openplantbook_api,
) -> None:
    """Clearing the cache removes the species state AND its registry entry."""
    await hass.services.async_call(
        DOMAIN, OPB_SERVICE_GET, {"species": "monstera deliciosa"}, blocking=True
    )
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get("openplantbook.monstera_deliciosa") is not None

    await hass.services.async_call(
        DOMAIN, OPB_SERVICE_CLEAN_CACHE, {ATTR_HOURS: 0}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("openplantbook.monstera_deliciosa") is None
    assert ent_reg.async_get("openplantbook.monstera_deliciosa") is None


async def test_species_entity_updates_on_refetch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_openplantbook_api,
) -> None:
    """Refetching an existing species updates its entity state in place."""
    await hass.services.async_call(
        DOMAIN, OPB_SERVICE_GET, {"species": "monstera deliciosa"}, blocking=True
    )
    assert hass.states.get("openplantbook.monstera_deliciosa") is not None

    # Return changed data and force a refetch (cache=false) for the same species.
    mock_openplantbook_api.async_plant_detail_get = AsyncMock(
        return_value={
            "pid": "monstera deliciosa",
            "display_pid": "Monstera deliciosa UPDATED",
            "max_light_lux": 20000,
            "min_light_lux": 1000,
        }
    )
    await hass.services.async_call(
        DOMAIN,
        OPB_SERVICE_GET,
        {"species": "monstera deliciosa", "cache": False},
        blocking=True,
    )

    state = hass.states.get("openplantbook.monstera_deliciosa")
    assert state is not None
    assert state.state == "Monstera deliciosa UPDATED"


async def test_species_entity_deduped_by_pid_across_inputs(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_openplantbook_api,
) -> None:
    """Different service inputs resolving to the same pid map to one entity.

    The entity holder is keyed by the canonical pid, so a second fetch with a
    differently-cased input updates the existing entity instead of attempting
    to add a duplicate with the same (already-taken) entity_id/unique_id.
    """
    # Both inputs resolve to the same pid; the second carries updated data.
    mock_openplantbook_api.async_plant_detail_get = AsyncMock(
        side_effect=[
            {
                "pid": "monstera deliciosa",
                "display_pid": "Monstera deliciosa",
                "max_light_lux": 20000,
                "min_light_lux": 1000,
            },
            {
                "pid": "monstera deliciosa",
                "display_pid": "Monstera deliciosa v2",
                "max_light_lux": 20000,
                "min_light_lux": 1000,
            },
        ]
    )

    await hass.services.async_call(
        DOMAIN, OPB_SERVICE_GET, {"species": "Monstera Deliciosa"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, OPB_SERVICE_GET, {"species": "monstera deliciosa"}, blocking=True
    )

    # Exactly one registry entry for the shared entity_id...
    ent_reg = er.async_get(hass)
    matching = [
        e
        for e in ent_reg.entities.values()
        if e.entity_id == "openplantbook.monstera_deliciosa"
    ]
    assert len(matching) == 1
    # ...and it reflects the second fetch (proving the update path was taken,
    # not a rejected duplicate add).
    state = hass.states.get("openplantbook.monstera_deliciosa")
    assert state is not None
    assert state.state == "Monstera deliciosa v2"
