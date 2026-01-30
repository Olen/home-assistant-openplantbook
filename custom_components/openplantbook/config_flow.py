"""Config flow for OpenPlantBook integration."""

from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_validation as cv
from openplantbook_sdk import MissingClientIdOrSecret

from . import OpenPlantBookApi
from .const import (
    ATTR_API,
    DEFAULT_IMAGE_PATH,
    DOMAIN,
    FLOW_DOWNLOAD_IMAGES,
    FLOW_DOWNLOAD_PATH,
    FLOW_UPLOAD_DATA,
    FLOW_UPLOAD_HASS_LOCATION_COORD,
    FLOW_UPLOAD_HASS_LOCATION_COUNTRY,
    OPB_CURRENT_INFO_MESSAGE,
    OPB_INFO_MESSAGE,
)

TITLE = "title"

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({CONF_CLIENT_ID: str, CONF_CLIENT_SECRET: str})
UPLOAD_SCHEMA = vol.Schema(
    {
        FLOW_UPLOAD_DATA: bool,
        FLOW_UPLOAD_HASS_LOCATION_COUNTRY: bool,
        FLOW_UPLOAD_HASS_LOCATION_COORD: bool,
    }
)


async def validate_input(hass: core.HomeAssistant, data: dict) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    # Check if values are not empty
    try:
        hass.data[DOMAIN][ATTR_API] = OpenPlantBookApi(
            data[CONF_CLIENT_ID], data[CONF_CLIENT_SECRET]
        )
        await hass.data[DOMAIN][ATTR_API]._async_get_token()
        # TODO 4: Error messages for "unable to connect" and "creds are not valid" not working well.
    except PermissionError as ex:
        raise ValueError from ex
    # If any of credentials are empty
    except (KeyError, MissingClientIdOrSecret) as ex:
        _LOGGER.debug("API client_id and/or client secret are invalid: %s", ex)
        raise ValueError from ex
    except Exception as ex:
        _LOGGER.error("Unable to connect to OpenPlantbook: %s", ex)
        raise

    return {TITLE: "Openplantbook API"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenPlantBook."""

    VERSION = 1

    data: dict[str, Any] | None

    @staticmethod
    @core.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except ValueError:
                errors[CONF_CLIENT_ID] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"

            if not errors:
                # Input is valid, set data.
                self.data = user_input
                # Skip upgrade message for new installations
                self.data[OPB_INFO_MESSAGE] = OPB_CURRENT_INFO_MESSAGE
                # Return the form of the next step.
                return await self.async_step_upload()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "apikey_url": "https://open.plantbook.io/apikey/show/"
            },
        )

    async def async_step_upload(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the upload step.

        Store it as ConfigEntry Options.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Openplantbook API", data=self.data, options=user_input
            )

        return self.async_show_form(
            step_id="upload",
            data_schema=UPLOAD_SCHEMA,
            errors=errors,
            description_placeholders={
                "sensor_data_url": "https://open.plantbook.io/ui/sensor-data/"
            },
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the OpenPlantbook integration."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self.errors: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        self.errors = {}
        download_images = self.config_entry.options.get(FLOW_DOWNLOAD_IMAGES, False)
        download_path = self.config_entry.options.get(
            FLOW_DOWNLOAD_PATH, DEFAULT_IMAGE_PATH
        )
        # Uploader settings
        upload_sensors = self.config_entry.options.get(FLOW_UPLOAD_DATA, False)
        location_country = self.config_entry.options.get(
            FLOW_UPLOAD_HASS_LOCATION_COUNTRY, False
        )
        location_coordinates = self.config_entry.options.get(
            FLOW_UPLOAD_HASS_LOCATION_COORD, False
        )

        if user_input is not None:
            _LOGGER.debug("User: %s", user_input)
            valid = await self.validate_input(user_input)
            if valid:
                return self.async_create_entry(title="", data=user_input)
            download_images = user_input.get(FLOW_DOWNLOAD_IMAGES)
            download_path = user_input.get(FLOW_DOWNLOAD_PATH)
            upload_sensors = user_input.get(FLOW_UPLOAD_DATA)
            location_country = user_input.get(FLOW_UPLOAD_HASS_LOCATION_COUNTRY)
            location_coordinates = user_input.get(FLOW_UPLOAD_HASS_LOCATION_COORD)

        _LOGGER.debug(
            "Init: %s, %s", self.config_entry.entry_id, self.config_entry.options
        )

        data_schema = {
            vol.Optional(FLOW_UPLOAD_DATA, default=upload_sensors): cv.boolean,
            vol.Optional(
                FLOW_UPLOAD_HASS_LOCATION_COUNTRY, default=location_country
            ): cv.boolean,
            vol.Optional(
                FLOW_UPLOAD_HASS_LOCATION_COORD, default=location_coordinates
            ): cv.boolean,
            vol.Optional(FLOW_DOWNLOAD_IMAGES, default=download_images): cv.boolean,
            vol.Optional(FLOW_DOWNLOAD_PATH, default=download_path): cv.string,
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema),
            errors=self.errors,
            description_placeholders={
                "sensor_data_url": "https://open.plantbook.io/ui/sensor-data/"
            },
        )

    async def validate_input(self, user_input: dict) -> bool:
        """Validate user input."""
        # If we dont want to download, dont worry about the path
        if not user_input.get(FLOW_DOWNLOAD_IMAGES):
            return True
        download_path = user_input.get(FLOW_DOWNLOAD_PATH)
        # If path is relative, we assume relative to Home Assistant config dir
        if not os.path.isabs(download_path):
            download_path = self.hass.config.path(download_path)

        if not os.path.isdir(download_path):
            _LOGGER.error(
                "Download path %s is invalid",
                download_path,
            )
            self.errors[FLOW_DOWNLOAD_PATH] = "invalid_path"
            return False
        return True
