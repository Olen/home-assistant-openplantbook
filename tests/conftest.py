"""Shared fixtures for openplantbook integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook.const import DOMAIN

# This fixture ensures our custom component is loaded
pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture(autouse=True)
def mock_recorder_dependency(hass: HomeAssistant) -> Generator[MagicMock, None, None]:
    """Mock recorder component to avoid dependency issues."""
    mock_instance = MagicMock()
    mock_instance.async_add_executor_job = AsyncMock(return_value={})

    with (
        patch(
            "custom_components.openplantbook.uploader.get_instance",
            return_value=mock_instance,
        ),
        patch(
            "custom_components.openplantbook.uploader.get_significant_states",
            return_value={},
        ),
        patch(
            "custom_components.openplantbook.uploader.get_last_state_changes",
            return_value={},
        ),
        patch(
            "homeassistant.loader.Integration.dependencies",
            new_callable=lambda: property(lambda self: []),
        ),
    ):
        yield mock_instance


# Standard test configuration
TEST_CLIENT_ID = "test_client_id"
TEST_CLIENT_SECRET = "test_client_secret"
TEST_ENTRY_ID = "test_entry_id_12345"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CLIENT_ID: TEST_CLIENT_ID,
            CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
        },
        options={},
        entry_id=TEST_ENTRY_ID,
        title="Openplantbook API",
    )


@pytest.fixture
def mock_openplantbook_api() -> Generator[MagicMock, None, None]:
    """Mock the OpenPlantBookApi."""
    with patch("custom_components.openplantbook.OpenPlantBookApi") as mock_api_class:
        mock_api = MagicMock()
        mock_api._async_get_token = AsyncMock(return_value="test_token")
        mock_api.async_plant_search = AsyncMock(
            return_value={
                "count": 1,
                "results": [
                    {
                        "pid": "monstera deliciosa",
                        "display_pid": "Monstera deliciosa",
                    }
                ],
            }
        )
        mock_api.async_plant_detail_get = AsyncMock(
            return_value={
                "pid": "monstera deliciosa",
                "display_pid": "Monstera deliciosa",
                "alias": "Swiss cheese plant",
                "image_url": "https://example.com/monstera.jpg",
                "min_temp": 15,
                "max_temp": 30,
                "min_soil_moist": 20,
                "max_soil_moist": 60,
                "min_light_lux": 1000,
                "max_light_lux": 20000,
                "min_soil_ec": 350,
                "max_soil_ec": 2000,
                "min_env_humid": 40,
                "max_env_humid": 80,
            }
        )
        mock_api.async_plant_instance_register = AsyncMock(
            return_value=[{"id": "test_instance_id", "latest_data": None}]
        )
        mock_api.async_plant_data_upload = AsyncMock(return_value=True)
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openplantbook_api: MagicMock,
) -> MockConfigEntry:
    """Set up the openplantbook integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
