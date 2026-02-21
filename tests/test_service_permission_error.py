from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook import InvalidAuth, async_setup_entry
from custom_components.openplantbook.const import (
    ATTR_IMAGE,
    ATTR_SPECIES,
    DOMAIN,
    FLOW_DOWNLOAD_IMAGES,
    FLOW_DOWNLOAD_PATH,
    OPB_DISPLAY_PID,
    OPB_PID,
    OPB_SERVICE_GET,
)

pytestmark = pytest.mark.enable_socket


@pytest.mark.asyncio
async def test_get_service_handles_permission_error_from_api(hass):
    api = AsyncMock()
    api.async_plant_detail_get = AsyncMock(
        side_effect=PermissionError("Authentication failed")
    )

    with patch("custom_components.openplantbook.OpenPlantBookApi", return_value=api):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_CLIENT_ID: "client", CONF_CLIENT_SECRET: "secret"},
            options={},
        )
        entry.add_to_hass(hass)
        assert await async_setup_entry(hass, entry)

    with pytest.raises(InvalidAuth):
        await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {ATTR_SPECIES: "capsicum annuum"},
            blocking=True,
        )

    assert "capsicum annuum" not in hass.data[DOMAIN][ATTR_SPECIES]


@pytest.mark.asyncio
async def test_get_service_handles_permission_error_when_writing_image(hass):
    plant_data = {
        OPB_PID: "capsicum annuum",
        OPB_DISPLAY_PID: "Capsicum annuum",
        ATTR_IMAGE: "https://example.com/capsicum.jpg",
    }

    api = AsyncMock()
    api.async_plant_detail_get = AsyncMock(return_value=plant_data)

    websession = Mock()
    resp = Mock()
    resp.status = 200
    resp.read = AsyncMock(return_value=b"image")
    websession.get = AsyncMock(return_value=resp)

    with (
        patch("custom_components.openplantbook.OpenPlantBookApi", return_value=api),
        patch(
            "custom_components.openplantbook.async_get_clientsession",
            return_value=websession,
        ),
        patch("custom_components.openplantbook.os.path.isfile", return_value=False),
        patch("builtins.open", side_effect=PermissionError("no permission")),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_CLIENT_ID: "client", CONF_CLIENT_SECRET: "secret"},
            options={
                FLOW_DOWNLOAD_IMAGES: True,
                FLOW_DOWNLOAD_PATH: "C:\\tmp",
            },
        )
        entry.add_to_hass(hass)
        assert await async_setup_entry(hass, entry)

        response = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {ATTR_SPECIES: "capsicum annuum"},
            blocking=True,
            return_response=True,
        )

    assert response[OPB_PID] == "capsicum annuum"
    state = hass.states.get("openplantbook.capsicum_annuum")
    assert state is not None
    assert state.attributes[ATTR_IMAGE] == "https://example.com/capsicum.jpg"
