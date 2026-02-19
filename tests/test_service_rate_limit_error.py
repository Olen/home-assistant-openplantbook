import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.exceptions import HomeAssistantError

from pytest_homeassistant_custom_component.common import MockConfigEntry

from openplantbook_sdk.sdk import RateLimitError

from custom_components.openplantbook import async_setup_entry
from custom_components.openplantbook.const import (
    ATTR_ALIAS,
    ATTR_SPECIES,
    DOMAIN,
    OPB_SERVICE_GET,
    OPB_SERVICE_SEARCH,
    OPB_SERVICE_UPLOAD,
)


pytestmark = pytest.mark.enable_socket


@pytest.mark.asyncio
async def test_get_service_handles_rate_limit_error(hass):
    api = AsyncMock()
    api.async_plant_detail_get = AsyncMock(side_effect=RateLimitError())

    with patch("custom_components.openplantbook.OpenPlantBookApi", return_value=api):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_CLIENT_ID: "client", CONF_CLIENT_SECRET: "secret"},
            options={},
        )
        entry.add_to_hass(hass)
        assert await async_setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {ATTR_SPECIES: "capsicum annuum"},
            blocking=True,
        )

    assert "capsicum annuum" not in hass.data[DOMAIN][ATTR_SPECIES]


@pytest.mark.asyncio
async def test_search_service_handles_rate_limit_error(hass):
    api = AsyncMock()
    api.async_plant_search = AsyncMock(side_effect=RateLimitError())

    with patch("custom_components.openplantbook.OpenPlantBookApi", return_value=api):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_CLIENT_ID: "client", CONF_CLIENT_SECRET: "secret"},
            options={},
        )
        entry.add_to_hass(hass)
        assert await async_setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_SEARCH,
            {ATTR_ALIAS: "capsicum"},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_upload_service_handles_rate_limit_error(hass):
    api = AsyncMock()

    with (
        patch("custom_components.openplantbook.OpenPlantBookApi", return_value=api),
        patch(
            "custom_components.openplantbook.plant_data_upload",
            new=AsyncMock(side_effect=RateLimitError()),
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_CLIENT_ID: "client", CONF_CLIENT_SECRET: "secret"},
            options={},
        )
        entry.add_to_hass(hass)
        assert await async_setup_entry(hass, entry)

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                OPB_SERVICE_UPLOAD,
                {},
                blocking=True,
            )
