"""Tests for the real OpenPlantbook entities and their unique_ids."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook.const import DOMAIN


async def test_search_result_entity_has_unique_id(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """The search_result entity is registered with a unique_id."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(f"{DOMAIN}.search_result")
    assert entry is not None
    assert entry.unique_id is not None


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
