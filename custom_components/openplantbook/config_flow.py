"""Config flow for OpenPlantBook integration."""
from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, core, data_entry_flow
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_validation as cv

from . import OpenPlantBookApi
from .const import (
    ATTR_API,
    DEFAULT_IMAGE_PATH,
    DOMAIN,
    FLOW_DOWNLOAD_IMAGES,
    FLOW_DOWNLOAD_PATH,
)

TITLE = "title"

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({CONF_CLIENT_ID: str, CONF_CLIENT_SECRET: str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    try:
        hass.data[DOMAIN][ATTR_API] = OpenPlantBookApi(
            data[CONF_CLIENT_ID], data[CONF_CLIENT_SECRET]
        )
    except Exception as ex:
        _LOGGER.debug("Unable to connect to OpenPlantbook: %s", ex)
        raise

    return {TITLE: "Openplantbook API"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenPlantBook."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    @staticmethod
    @core.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info[TITLE], data=user_input)
            except Exception as ex:
                _LOGGER.error("Unable to connect to OpenPlantbook: %s", ex)
                raise

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handling opetions for plant"""

    def __init__(
        self,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize options flow."""

        entry.async_on_unload(entry.add_update_listener(self.update_plantbook_options))
        self.entry = entry
        self.errors = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Manage the options."""
        self.errors = {}
        download_images = self.entry.options.get(FLOW_DOWNLOAD_IMAGES, False)
        download_path = self.entry.options.get(FLOW_DOWNLOAD_PATH, DEFAULT_IMAGE_PATH)

        if user_input is not None:
            _LOGGER.debug("User: %s", user_input)
            valid = await self.validate_input(user_input)
            if valid:
                return self.async_create_entry(title="", data=user_input)
            download_images = user_input.get(FLOW_DOWNLOAD_IMAGES)
            download_path = user_input.get(FLOW_DOWNLOAD_PATH)

        _LOGGER.debug(
            "Init: %s, %s, %s", self.entry.entry_id, self.entry.data, self.entry.options
        )

        data_schema = {}
        data_schema[
            vol.Optional(FLOW_DOWNLOAD_IMAGES, default=download_images)
        ] = cv.boolean
        data_schema[vol.Optional(FLOW_DOWNLOAD_PATH, default=download_path)] = cv.string

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(data_schema), errors=self.errors
        )

    async def validate_input(self, user_input):
        """Validating input"""
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

    async def update_plantbook_options(
        self, hass: core.HomeAssistant, entry: config_entries.ConfigEntry
    ):
        """Updating plantbook options"""
        _LOGGER.debug("Update: %s, %s, %s", entry.entry_id, entry.data, entry.options)
