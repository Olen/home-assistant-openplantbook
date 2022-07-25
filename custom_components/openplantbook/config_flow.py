"""Config flow for OpenPlantBook integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

from . import OpenPlantBookApi
from .const import ATTR_API, DOMAIN

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
