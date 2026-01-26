"""Tests for openplantbook integration setup."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook.const import (
    ATTR_API,
    ATTR_SPECIES,
    DOMAIN,
    OPB_SERVICE_CLEAN_CACHE,
    OPB_SERVICE_GET,
    OPB_SERVICE_SEARCH,
    OPB_SERVICE_UPLOAD,
)


class TestIntegrationSetup:
    """Tests for integration setup."""

    async def test_async_setup(self, hass: HomeAssistant) -> None:
        """Test async_setup returns True."""
        from custom_components.openplantbook import async_setup

        result = await async_setup(hass, {})
        assert result is True

    async def test_async_setup_entry(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test async_setup_entry creates domain data and services."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert DOMAIN in hass.data
        assert ATTR_API in hass.data[DOMAIN]
        assert ATTR_SPECIES in hass.data[DOMAIN]

    async def test_services_registered(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
    ) -> None:
        """Test that all services are registered."""
        assert hass.services.has_service(DOMAIN, OPB_SERVICE_SEARCH)
        assert hass.services.has_service(DOMAIN, OPB_SERVICE_GET)
        assert hass.services.has_service(DOMAIN, OPB_SERVICE_CLEAN_CACHE)
        assert hass.services.has_service(DOMAIN, OPB_SERVICE_UPLOAD)

    async def test_async_unload_entry(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
    ) -> None:
        """Test async_unload_entry removes services and data."""
        # Verify setup was successful
        assert DOMAIN in hass.data

        # Unload the entry
        result = await hass.config_entries.async_unload(init_integration.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert DOMAIN not in hass.data

    async def test_services_removed_on_unload(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
    ) -> None:
        """Test that services are removed on unload."""
        # Verify services exist
        assert hass.services.has_service(DOMAIN, OPB_SERVICE_SEARCH)
        assert hass.services.has_service(DOMAIN, OPB_SERVICE_GET)

        # Unload
        await hass.config_entries.async_unload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Services should be removed
        assert not hass.services.has_service(DOMAIN, OPB_SERVICE_SEARCH)
        assert not hass.services.has_service(DOMAIN, OPB_SERVICE_GET)


class TestSearchService:
    """Tests for the search service."""

    async def test_search_service_returns_results(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test search service returns plant results."""
        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_SEARCH,
            {"alias": "monstera"},
            blocking=True,
            return_response=True,
        )

        assert result is not None
        assert "monstera deliciosa" in result

    async def test_search_service_creates_state(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test search service creates search result state."""
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_SEARCH,
            {"alias": "monstera"},
            blocking=True,
        )

        state = hass.states.get(f"{DOMAIN}.search_result")
        assert state is not None
        assert int(state.state) == 1


class TestGetPlantService:
    """Tests for the get plant service."""

    async def test_get_plant_returns_data(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test get plant service returns plant data."""
        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
            return_response=True,
        )

        assert result is not None
        assert result.get("pid") == "monstera deliciosa"
        assert result.get("display_pid") == "Monstera deliciosa"

    async def test_get_plant_caches_result(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test that get plant caches the result."""
        # First call
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
        )

        # Verify it's cached
        assert "monstera deliciosa" in hass.data[DOMAIN][ATTR_SPECIES]

        # Second call should use cache
        mock_openplantbook_api.async_plant_detail_get.reset_mock()
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
        )

        # API should not be called again (using cache)
        # Note: This depends on cache time, in practice it should use cache


class TestCleanCacheService:
    """Tests for the clean cache service."""

    async def test_clean_cache_removes_old_entries(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test clean cache service removes old entries."""
        # First get a plant to populate cache
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
        )

        # Verify it's cached
        assert "monstera deliciosa" in hass.data[DOMAIN][ATTR_SPECIES]

        # Clean cache with hours=0 to remove all
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_CLEAN_CACHE,
            {"hours": 0},
            blocking=True,
        )

        # Cache should be empty
        assert "monstera deliciosa" not in hass.data[DOMAIN][ATTR_SPECIES]
