"""The OpenPlantBook integration."""
import asyncio
from datetime import datetime, timedelta
import logging
import os
import re
import urllib.parse

import async_timeout
from pyopenplantbook import MissingClientIdOrSecret, OpenPlantBookApi
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import raise_if_invalid_filename, slugify

from .const import (
    ATTR_ALIAS,
    ATTR_API,
    ATTR_HOURS,
    ATTR_IMAGE,
    ATTR_SPECIES,
    CACHE_TIME,
    DOMAIN,
    FLOW_DOWNLOAD_IMAGES,
    FLOW_DOWNLOAD_PATH,
    OPB_ATTR_RESULTS,
    OPB_ATTR_SEARCH_RESULT,
    OPB_ATTR_TIMESTAMP,
    OPB_DISPLAY_PID,
    OPB_PID,
    OPB_SERVICE_CLEAN_CACHE,
    OPB_SERVICE_GET,
    OPB_SERVICE_SEARCH,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the OpenPlantBook component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up OpenPlantBook from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if ATTR_API not in hass.data[DOMAIN]:
        hass.data[DOMAIN][ATTR_API] = OpenPlantBookApi(
            entry.data.get(CONF_CLIENT_ID), entry.data.get(CONF_CLIENT_SECRET)
        )
    if ATTR_SPECIES not in hass.data[DOMAIN]:
        hass.data[DOMAIN][ATTR_SPECIES] = {}

    async def get_plant(call):
        if DOMAIN not in hass.data:
            return
        species = call.data.get(ATTR_SPECIES)
        if species:
            # Here we try to ensure that we only run one API request for each species
            # The first process creates an empty dict, and access the API
            # Later requests for the same species either wait for the first one to complete
            # or they returns immediately if we already have the data we need
            _LOGGER.debug("get_plant %s", species)
            if species not in hass.data[DOMAIN][ATTR_SPECIES]:
                _LOGGER.debug("I am the first process to get %s", species)
                hass.data[DOMAIN][ATTR_SPECIES][species] = {}
            elif OPB_PID not in hass.data[DOMAIN][ATTR_SPECIES][species]:
                # If more than one "get_plant" is triggered for the same species, we wait for up to
                # 10 seconds for the first process to complete the API request.
                # We don't want to return immediately, as we want the state object to be set by
                # the running process before we return from this call
                _LOGGER.debug(
                    "Another process is currently trying to get the data for %s",
                    species,
                )

                wait = 0
                while OPB_PID not in hass.data[DOMAIN][ATTR_SPECIES][species]:
                    _LOGGER.debug("Waiting")
                    wait = wait + 1
                    if wait == 10:
                        _LOGGER.error("Giving up waiting for OpenPlantBook")
                        return False
                    await asyncio.sleep(1)
                _LOGGER.debug("The other process completed successfully")
                return True
            elif datetime.now() < datetime.fromisoformat(
                hass.data[DOMAIN][ATTR_SPECIES][species][OPB_ATTR_TIMESTAMP]
            ) + timedelta(hours=CACHE_TIME):
                # We already have the data we need, so let's just return
                _LOGGER.debug("We already have cached data for %s", species)
                return True
            try:
                plant_data = await hass.data[DOMAIN][ATTR_API].get_plantbook_data(
                    species
                )
            except MissingClientIdOrSecret:
                plant_data = None
                _LOGGER.error(
                    "Missing client ID or secret. Please set up the integration again"
                )

            if plant_data:
                _LOGGER.debug("Got data for %s", species)
                plant_data[OPB_ATTR_TIMESTAMP] = datetime.now().isoformat()
                hass.data[DOMAIN][ATTR_SPECIES][species] = plant_data
                attrs = {}
                for var, val in plant_data.items():
                    attrs[var] = val
                entity_id = async_generate_entity_id(
                    f"{DOMAIN}.{{}}", plant_data[OPB_PID], current_ids={}
                )
                if entry.options.get(FLOW_DOWNLOAD_IMAGES) and plant_data.get(
                    ATTR_IMAGE
                ):
                    filename = slugify(
                        urllib.parse.unquote(os.path.basename(plant_data[ATTR_IMAGE])),
                        separator=" ",
                    ).replace(" jpg", ".jpg")
                    raise_if_invalid_filename(filename)
                    download_path = entry.options.get(FLOW_DOWNLOAD_PATH)
                    if not os.path.isabs(download_path):
                        download_path = hass.config.path(download_path)

                    final_path = os.path.join(download_path, filename)
                    if os.path.isfile(final_path):
                        _LOGGER.warning("Filename %s already exists", final_path)
                        downloaded_file = final_path
                    else:
                        downloaded_file = await async_download_image(
                            plant_data.get(ATTR_IMAGE), final_path
                        )
                    if downloaded_file and "www/" in downloaded_file:
                        attrs[ATTR_IMAGE] = re.sub(
                            "^.*www/", "/local/", downloaded_file
                        )

                hass.states.async_set(entity_id, plant_data[OPB_DISPLAY_PID], attrs)

            else:
                del hass.data[DOMAIN][ATTR_SPECIES][species]

    async def search_plantbook(call):
        alias = call.data.get(ATTR_ALIAS)
        if DOMAIN not in hass.data:
            return
        if alias:
            _LOGGER.info("Searching for %s", alias)
            try:
                plant_data = await hass.data[DOMAIN][ATTR_API].search_plantbook(alias)
            except MissingClientIdOrSecret:
                plant_data = None
                _LOGGER.error(
                    "Missing client ID or secret. Please set up the integration again"
                )
                return
            state = len(plant_data[OPB_ATTR_RESULTS])
            attrs = {}
            for plant in plant_data[OPB_ATTR_RESULTS]:
                pid = plant[OPB_PID]
                attrs[pid] = plant[OPB_DISPLAY_PID]
            hass.states.async_set(f"{DOMAIN}.{OPB_ATTR_SEARCH_RESULT}", state, attrs)

    async def clean_cache(call):
        hours = call.data.get(ATTR_HOURS)
        if hours is None or not isinstance(hours, int):
            hours = CACHE_TIME
        if ATTR_SPECIES in hass.data[DOMAIN]:
            for species in list(hass.data[DOMAIN][ATTR_SPECIES]):
                value = hass.data[DOMAIN][ATTR_SPECIES][species]
                if datetime.now() > datetime.fromisoformat(
                    value[OPB_ATTR_TIMESTAMP]
                ) + timedelta(hours=hours):
                    _LOGGER.debug("Removing %s from cache", species)
                    entity_id = async_generate_entity_id(
                        f"{DOMAIN}.{{}}", value[OPB_PID], current_ids={}
                    )
                    hass.states.async_remove(entity_id)
                    hass.data[DOMAIN][ATTR_SPECIES].pop(species)

    async def async_download_image(url, download_to):
        _LOGGER.debug(
            "Going to download image %s to %s",
            url,
            download_to,
        )
        if os.path.isfile(download_to):
            _LOGGER.warning(
                "File %s already exists. Will not download again", download_to
            )
            return download_to
        websession = async_get_clientsession(hass)

        with async_timeout.timeout(10):
            resp = await websession.get(url)
            if resp.status != 200:
                _LOGGER.warning(
                    "Downloading '%s' failed, status_code=%d", url, resp.status
                )
                return False

        data = await resp.read()
        with open(download_to, "wb") as fil:
            fil.write(data)

        _LOGGER.debug("Downloading of %s done", url)
        return download_to

    hass.services.async_register(DOMAIN, OPB_SERVICE_SEARCH, search_plantbook)
    hass.services.async_register(DOMAIN, OPB_SERVICE_GET, get_plant)
    hass.services.async_register(DOMAIN, OPB_SERVICE_CLEAN_CACHE, clean_cache)
    hass.states.async_set(f"{DOMAIN}.{OPB_ATTR_SEARCH_RESULT}", 0)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.debug("Unloading %s", DOMAIN)
    _LOGGER.debug("Removing cache")
    await hass.services.async_call(
        domain=DOMAIN,
        service=OPB_SERVICE_CLEAN_CACHE,
        service_data={ATTR_HOURS: 0},
        blocking=True,
        limit=30,
    )
    _LOGGER.debug("Removing search result")
    hass.states.async_remove(f"{DOMAIN}.{OPB_ATTR_SEARCH_RESULT}")
    _LOGGER.debug("Removing services")
    hass.services.async_remove(DOMAIN, OPB_SERVICE_SEARCH)
    hass.services.async_remove(DOMAIN, OPB_SERVICE_GET)
    hass.services.async_remove(DOMAIN, OPB_SERVICE_CLEAN_CACHE)
    # And we get rid of the rest
    hass.data.pop(DOMAIN)

    return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
