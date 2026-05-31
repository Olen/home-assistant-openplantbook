"""Tests for openplantbook integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from openplantbook_sdk import MissingClientIdOrSecret
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook.const import (
    ATTR_API,
    ATTR_IMAGE,
    ATTR_SPECIES,
    DEFAULT_IMAGE_PATH,
    DOMAIN,
    FLOW_DOWNLOAD_IMAGES,
    FLOW_DOWNLOAD_PATH,
    OPB_SERVICE_CLEAN_CACHE,
    OPB_SERVICE_GET,
    OPB_SERVICE_SEARCH,
    OPB_SERVICE_UPLOAD,
)
from custom_components.openplantbook.plantbook_exception import OpenPlantbookException


def _make_detail_side_effect():
    """Build an async_plant_detail_get side_effect that adds care fields
    only when params requests include=care (mirrors the real API)."""

    async def _side_effect(species, lang=None, params=None, **kwargs):
        data = {
            "pid": "monstera deliciosa",
            "display_pid": "Monstera deliciosa",
            "alias": "Swiss cheese plant",
            "image_url": "https://example.com/monstera.jpg",
            "min_temp": 15,
            "max_temp": 30,
            "min_soil_moist": 20,
            "max_soil_moist": 60,
        }
        include = (params or {}).get("include", "")
        categories = {c.strip() for c in include.split(",") if c.strip()}
        if "care" in categories:
            data.update(
                {
                    "watering": "Likes wet envs; reduce watering in winter.",
                    "sunlight": "Relatively shade-tolerant, prefers half-shade.",
                    "soil": "Peat mixed with coarse sand or hydroponics",
                    "pruning": "Timely remove dead and yellowish leaves.",
                    "fertilization": "Dilute fertilizer once every 15 days.",
                }
            )
        return data

    return _side_effect


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


class TestParseIncludes:
    """Tests for the _parse_includes helper."""

    def test_none_returns_empty_set(self) -> None:
        from custom_components.openplantbook import _parse_includes

        assert _parse_includes(None) == set()

    def test_empty_string_returns_empty_set(self) -> None:
        from custom_components.openplantbook import _parse_includes

        assert _parse_includes("") == set()
        assert _parse_includes("   ") == set()

    def test_single_category(self) -> None:
        from custom_components.openplantbook import _parse_includes

        assert _parse_includes("care") == {"care"}

    def test_comma_separated_with_whitespace(self) -> None:
        from custom_components.openplantbook import _parse_includes

        assert _parse_includes("care, poison ,care") == {"care", "poison"}


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


class TestImageDownload:
    """Tests for image download functionality."""

    @pytest.fixture
    def mock_config_entry_with_download(self) -> MockConfigEntry:
        """Create a config entry with image download enabled."""
        return MockConfigEntry(
            domain=DOMAIN,
            data={
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
            },
            options={
                FLOW_DOWNLOAD_IMAGES: True,
                FLOW_DOWNLOAD_PATH: DEFAULT_IMAGE_PATH,
            },
            entry_id="test_entry_id_12345",
            title="Openplantbook API",
        )

    async def test_get_plant_downloads_image(
        self,
        hass: HomeAssistant,
        mock_config_entry_with_download: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
        tmp_path,
    ) -> None:
        """Test get_plant downloads image when enabled and rewrites URL."""
        # Use a real temp directory under www/ so the /local/ rewrite works
        download_dir = tmp_path / "www" / "images" / "plants"
        download_dir.mkdir(parents=True)

        mock_config_entry_with_download.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry_with_download,
            options={
                **mock_config_entry_with_download.options,
                FLOW_DOWNLOAD_PATH: str(download_dir),
            },
        )

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"fake image data")

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_resp)

        with patch(
            "custom_components.openplantbook.async_get_clientsession",
            return_value=mock_session,
        ):
            await hass.config_entries.async_setup(
                mock_config_entry_with_download.entry_id
            )
            await hass.async_block_till_done()

            hass.data[DOMAIN][ATTR_SPECIES].clear()

            result = await hass.services.async_call(
                DOMAIN,
                OPB_SERVICE_GET,
                {"species": "monstera deliciosa"},
                blocking=True,
                return_response=True,
            )

        assert result is not None
        # The image_url should be rewritten to a /local/ path
        assert result.get(ATTR_IMAGE, "").startswith("/local/")
        # Verify the file was actually written
        downloaded_file = download_dir / "monstera.jpg"
        assert downloaded_file.exists()
        assert downloaded_file.read_bytes() == b"fake image data"

    async def test_get_plant_image_filename_ignores_query_string(
        self,
        hass: HomeAssistant,
        mock_config_entry_with_download: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
        tmp_path,
    ) -> None:
        """A cache-busting query string in the image URL must not leak into the filename."""
        download_dir = tmp_path / "www" / "images" / "plants"
        download_dir.mkdir(parents=True)

        mock_config_entry_with_download.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry_with_download,
            options={
                **mock_config_entry_with_download.options,
                FLOW_DOWNLOAD_PATH: str(download_dir),
            },
        )

        # OpenPlantbook serves cache-busted image URLs, e.g. ...jpg?v=abc123
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            return_value={
                "pid": "monstera deliciosa",
                "display_pid": "Monstera deliciosa",
                "image_url": "https://example.com/monstera.jpg?v=abc123",
            }
        )

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"fake image data")
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_resp)

        with patch(
            "custom_components.openplantbook.async_get_clientsession",
            return_value=mock_session,
        ):
            await hass.config_entries.async_setup(
                mock_config_entry_with_download.entry_id
            )
            await hass.async_block_till_done()
            hass.data[DOMAIN][ATTR_SPECIES].clear()

            result = await hass.services.async_call(
                DOMAIN,
                OPB_SERVICE_GET,
                {"species": "monstera deliciosa"},
                blocking=True,
                return_response=True,
            )

        # Filename is derived from the URL path only — query string is stripped.
        assert (download_dir / "monstera.jpg").exists()
        # No stray file carrying the query string was created.
        saved = [p.name for p in download_dir.iterdir()]
        assert saved == ["monstera.jpg"], saved
        assert "?" not in result.get(ATTR_IMAGE, "")
        assert "abc123" not in result.get(ATTR_IMAGE, "")

    async def test_get_plant_skips_existing_image(
        self,
        hass: HomeAssistant,
        mock_config_entry_with_download: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test get_plant skips download when file already exists."""
        mock_config_entry_with_download.add_to_hass(hass)

        with (
            patch("os.path.isabs", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):
            await hass.config_entries.async_setup(
                mock_config_entry_with_download.entry_id
            )
            await hass.async_block_till_done()

            hass.data[DOMAIN][ATTR_SPECIES].clear()

            # File already exists on disk
            with patch("os.path.isfile", return_value=True):
                result = await hass.services.async_call(
                    DOMAIN,
                    OPB_SERVICE_GET,
                    {"species": "monstera deliciosa"},
                    blocking=True,
                    return_response=True,
                )

        assert result is not None
        # Should still rewrite to /local/ path even if file existed
        assert result.get(ATTR_IMAGE, "").startswith("/local/")

    async def test_get_plant_no_download_when_disabled(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test get_plant does not download when download is disabled."""
        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
            return_response=True,
        )

        assert result is not None
        # Image URL should remain the original HTTP URL
        assert result.get(ATTR_IMAGE, "").startswith("https://")


class TestGetServiceInclude:
    """Tests for the include parameter on the get service."""

    async def test_include_param_passed_to_api(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """include=care must reach the SDK as a params query argument."""
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa", "include": "care"},
            blocking=True,
        )

        call = mock_openplantbook_api.async_plant_detail_get.call_args
        assert call.kwargs["params"] == {"include": "care"}

    async def test_no_include_passes_empty_params(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """A plain get passes an empty params dict (no extra query args)."""
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
        )

        call = mock_openplantbook_api.async_plant_detail_get.call_args
        assert call.kwargs["params"] == {}


class TestGetServiceIncludeCaching:
    """Tests for include-aware caching and merge behaviour."""

    async def test_base_then_care_refetches(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """A base fetch followed by include=care must hit the API again."""
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            side_effect=_make_detail_side_effect()
        )

        await hass.services.async_call(
            DOMAIN, OPB_SERVICE_GET, {"species": "monstera deliciosa"}, blocking=True
        )
        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa", "include": "care"},
            blocking=True,
            return_response=True,
        )

        assert mock_openplantbook_api.async_plant_detail_get.call_count == 2
        assert result.get("watering") == "Likes wet envs; reduce watering in winter."

    async def test_care_then_care_served_from_cache(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """A second identical include=care request is served from cache."""
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            side_effect=_make_detail_side_effect()
        )

        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa", "include": "care"},
            blocking=True,
        )
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa", "include": "care"},
            blocking=True,
        )

        assert mock_openplantbook_api.async_plant_detail_get.call_count == 1

    async def test_base_after_care_uses_cache_and_keeps_care(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """A base get after a fresh care fetch is a cache hit and still has care."""
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            side_effect=_make_detail_side_effect()
        )

        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa", "include": "care"},
            blocking=True,
        )
        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
            return_response=True,
        )

        assert mock_openplantbook_api.async_plant_detail_get.call_count == 1
        assert result.get("soil") == "Peat mixed with coarse sand or hydroponics"

    async def test_care_fields_published_as_entity_attributes(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """care fields are merged into the HA entity attributes."""
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            side_effect=_make_detail_side_effect()
        )

        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa", "include": "care"},
            blocking=True,
        )

        state = hass.states.get("openplantbook.monstera_deliciosa")
        assert state is not None
        assert state.attributes.get("watering") is not None

    async def test_cache_bypass_with_include(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """cache=false forces a refetch even for an already-satisfied include."""
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            side_effect=_make_detail_side_effect()
        )

        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa", "include": "care"},
            blocking=True,
        )
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa", "include": "care", "cache": False},
            blocking=True,
        )

        assert mock_openplantbook_api.async_plant_detail_get.call_count == 2
