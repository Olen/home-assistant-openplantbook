"""Tests for openplantbook config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from openplantbook_sdk import MissingClientIdOrSecret
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook.const import (
    DEFAULT_IMAGE_PATH,
    DOMAIN,
    FLOW_DOWNLOAD_IMAGES,
    FLOW_DOWNLOAD_PATH,
    FLOW_UPLOAD_DATA,
    FLOW_UPLOAD_HASS_LOCATION_COORD,
    FLOW_UPLOAD_HASS_LOCATION_COUNTRY,
)


class TestConfigFlow:
    """Tests for the config flow."""

    async def test_user_step_shows_form(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that the user step shows the form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_user_step_invalid_auth(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that invalid auth shows error."""
        with patch(
            "custom_components.openplantbook.config_flow.OpenPlantBookApi"
        ) as mock_api_class:
            mock_api = MagicMock()
            mock_api._async_get_token = AsyncMock(
                side_effect=MissingClientIdOrSecret("Invalid credentials")
            )
            mock_api_class.return_value = mock_api

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_CLIENT_ID: "invalid_id",
                    CONF_CLIENT_SECRET: "invalid_secret",
                },
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "user"
            assert result["errors"] == {CONF_CLIENT_ID: "invalid_auth"}

    async def test_user_step_cannot_connect(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that connection error shows error."""
        with patch(
            "custom_components.openplantbook.config_flow.OpenPlantBookApi"
        ) as mock_api_class:
            mock_api = MagicMock()
            mock_api._async_get_token = AsyncMock(
                side_effect=ConnectionError("Cannot connect")
            )
            mock_api_class.return_value = mock_api

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_CLIENT_ID: "test_id",
                    CONF_CLIENT_SECRET: "test_secret",
                },
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "user"
            assert result["errors"] == {"base": "cannot_connect"}

    async def test_user_step_success_goes_to_upload(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that valid credentials proceed to upload step."""
        with patch(
            "custom_components.openplantbook.config_flow.OpenPlantBookApi"
        ) as mock_api_class:
            mock_api = MagicMock()
            mock_api._async_get_token = AsyncMock(return_value="test_token")
            mock_api_class.return_value = mock_api

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_CLIENT_ID: "valid_id",
                    CONF_CLIENT_SECRET: "valid_secret",
                },
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "upload"

    async def test_upload_step_creates_entry(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that upload step creates the config entry."""
        with patch(
            "custom_components.openplantbook.config_flow.OpenPlantBookApi"
        ) as mock_api_class:
            mock_api = MagicMock()
            mock_api._async_get_token = AsyncMock(return_value="test_token")
            mock_api_class.return_value = mock_api

            # Start flow
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            # Complete user step
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_CLIENT_ID: "valid_id",
                    CONF_CLIENT_SECRET: "valid_secret",
                },
            )

            # Complete upload step
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    FLOW_UPLOAD_DATA: True,
                    FLOW_UPLOAD_HASS_LOCATION_COUNTRY: False,
                    FLOW_UPLOAD_HASS_LOCATION_COORD: False,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "Openplantbook API"
            assert result["data"][CONF_CLIENT_ID] == "valid_id"
            assert result["data"][CONF_CLIENT_SECRET] == "valid_secret"
            assert result["options"][FLOW_UPLOAD_DATA] is True


class TestOptionsFlow:
    """Tests for the options flow."""

    async def test_options_flow_init(
        self,
        hass: HomeAssistant,
        mock_openplantbook_api: MagicMock,
        init_integration: MockConfigEntry,
    ) -> None:
        """Test options flow initialization."""
        result = await hass.config_entries.options.async_init(init_integration.entry_id)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_save(
        self,
        hass: HomeAssistant,
        mock_openplantbook_api: MagicMock,
        init_integration: MockConfigEntry,
    ) -> None:
        """Test saving options."""
        result = await hass.config_entries.options.async_init(init_integration.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                FLOW_UPLOAD_DATA: True,
                FLOW_UPLOAD_HASS_LOCATION_COUNTRY: True,
                FLOW_UPLOAD_HASS_LOCATION_COORD: False,
                FLOW_DOWNLOAD_IMAGES: False,
                FLOW_DOWNLOAD_PATH: DEFAULT_IMAGE_PATH,
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][FLOW_UPLOAD_DATA] is True
        assert result["data"][FLOW_UPLOAD_HASS_LOCATION_COUNTRY] is True

    async def test_options_flow_invalid_download_path(
        self,
        hass: HomeAssistant,
        mock_openplantbook_api: MagicMock,
        init_integration: MockConfigEntry,
    ) -> None:
        """Test that invalid download path shows error."""
        result = await hass.config_entries.options.async_init(init_integration.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                FLOW_UPLOAD_DATA: False,
                FLOW_UPLOAD_HASS_LOCATION_COUNTRY: False,
                FLOW_UPLOAD_HASS_LOCATION_COORD: False,
                FLOW_DOWNLOAD_IMAGES: True,
                FLOW_DOWNLOAD_PATH: "/nonexistent/path/that/does/not/exist",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] == {FLOW_DOWNLOAD_PATH: "invalid_path"}

    async def test_options_flow_download_disabled_ignores_path(
        self,
        hass: HomeAssistant,
        mock_openplantbook_api: MagicMock,
        init_integration: MockConfigEntry,
    ) -> None:
        """Test that download path is ignored when download is disabled."""
        result = await hass.config_entries.options.async_init(init_integration.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                FLOW_UPLOAD_DATA: False,
                FLOW_UPLOAD_HASS_LOCATION_COUNTRY: False,
                FLOW_UPLOAD_HASS_LOCATION_COORD: False,
                FLOW_DOWNLOAD_IMAGES: False,
                FLOW_DOWNLOAD_PATH: "/nonexistent/path",
            },
        )

        # Should succeed because download is disabled
        assert result["type"] == FlowResultType.CREATE_ENTRY
