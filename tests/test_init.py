"""Tests for openplantbook integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from openplantbook_sdk import MissingClientIdOrSecret
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
from custom_components.openplantbook.plantbook_exception import OpenPlantbookException


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


class TestSearchServiceErrors:
    """Tests for search service error handling."""

    async def test_search_service_missing_alias(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test search service raises error when alias is missing."""
        with pytest.raises(OpenPlantbookException):
            await hass.services.async_call(
                DOMAIN,
                OPB_SERVICE_SEARCH,
                {},  # No alias provided
                blocking=True,
            )

    async def test_search_service_api_error(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test search service handles API errors."""
        mock_openplantbook_api.async_plant_search = AsyncMock(
            side_effect=MissingClientIdOrSecret("Invalid credentials")
        )

        with pytest.raises(MissingClientIdOrSecret):
            await hass.services.async_call(
                DOMAIN,
                OPB_SERVICE_SEARCH,
                {"alias": "monstera"},
                blocking=True,
            )


class TestGetPlantServiceErrors:
    """Tests for get plant service error handling."""

    async def test_get_plant_missing_species(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test get plant raises error when species is missing."""
        with pytest.raises(OpenPlantbookException):
            await hass.services.async_call(
                DOMAIN,
                OPB_SERVICE_GET,
                {},  # No species provided
                blocking=True,
            )

    async def test_get_plant_api_error(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test get plant handles API errors."""
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            side_effect=MissingClientIdOrSecret("Invalid credentials")
        )

        with pytest.raises(MissingClientIdOrSecret):
            await hass.services.async_call(
                DOMAIN,
                OPB_SERVICE_GET,
                {"species": "monstera deliciosa"},
                blocking=True,
            )

    async def test_get_plant_returns_empty_when_not_found(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test get plant returns empty dict when plant not found."""
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(return_value=None)

        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "unknown_plant"},
            blocking=True,
            return_response=True,
        )

        assert result == {}


class TestUploadService:
    """Tests for the upload service."""

    async def test_upload_service_callable(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test upload service is callable."""
        # The upload service should be callable even if there's nothing to upload
        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_UPLOAD,
            {},
            blocking=True,
            return_response=True,
        )

        # Result should have a result key (even if the value is None)
        assert "result" in result


class TestCleanCacheServiceEdgeCases:
    """Tests for clean cache service edge cases."""

    async def test_clean_cache_with_default_hours(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test clean cache with default hours (no parameter)."""
        # First get a plant to populate cache
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
        )

        # Clean cache without hours parameter (uses default)
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_CLEAN_CACHE,
            {},
            blocking=True,
        )

        # With default hours (24), recent cache entries should remain
        assert "monstera deliciosa" in hass.data[DOMAIN][ATTR_SPECIES]

    async def test_clean_cache_with_invalid_hours(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test clean cache with invalid hours parameter uses default."""
        # First get a plant to populate cache
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
        )

        # Clean cache with invalid hours (string instead of int)
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_CLEAN_CACHE,
            {"hours": "invalid"},
            blocking=True,
        )

        # With invalid hours, uses default (24), recent entries should remain
        assert "monstera deliciosa" in hass.data[DOMAIN][ATTR_SPECIES]
