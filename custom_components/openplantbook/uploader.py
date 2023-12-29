from datetime import timedelta, datetime
from typing import Any

from json_timeseries import JtsDocument, TsRecord, TimeSeries

import homeassistant.util.dt as dt_util
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states, \
    get_last_state_changes
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    callback,
    Event,
    HassJob
)
from homeassistant.helpers import device_registry
from homeassistant.helpers import entity_registry
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.util import dt
from .plantbook_exception import OpenPlantbookException
from .const import DOMAIN, OPB_MEASUREMENTS_TO_UPLOAD, ATTR_API, FLOW_UPLOAD_DATA, FLOW_UPLOAD_HASS_LOCATION_COUNTRY, \
    FLOW_UPLOAD_HASS_LOCATION_COORD
import logging

UPLOAD_TIME_INTERVAL = timedelta(minutes=30)
UPLOAD_WAIT_AFTER_RESTART = timedelta(minutes=5)
# TODO 4: change time to once a day

_LOGGER = logging.getLogger(__name__)


async def plant_data_upload(hass, entry, call=None) -> dict[str, Any] | None:
    if DOMAIN not in hass.data:
        raise OpenPlantbookException("no data found for domain %s", DOMAIN)
    # _device_id = call.data.get(ATTR_PLANT_INSTANCE)

    if call:
        _LOGGER.info("Plant-sensors data upload service is triggered")

    # def device_entities(hass: HomeAssistant, _device_id: str) -> Iterable[str]:

    _LOGGER.debug("Querying Plants' sensors data for upload")

    # Get location data as per selected Options
    location = {}
    if entry.options.get(FLOW_UPLOAD_HASS_LOCATION_COUNTRY):
        location["country"] = hass.config.country

    if entry.options.get(FLOW_UPLOAD_HASS_LOCATION_COORD):
        location["lon"] = hass.config.longitude
        location["lat"] = hass.config.latitude

    # Get entity ids for plant devices.
    device_reg = device_registry.async_get(hass)
    # device_reg_i = device_registry.DeviceRegistryItems()
    # devices = device_registry.async_get_device(hass)

    plant_devices = []
    # Looking for Plant-component's devices
    for i, d in device_reg.devices.data.items():
        if 'plant' in str(d.identifiers) and d.name_by_user is None:
            plant_devices.append(d)

    entity_reg = entity_registry.async_get(hass)
    jts_doc = JtsDocument()

    # Go through plant devices one by one and extract corresponding sensors' states
    for i in plant_devices:

        # Get entity ids for plant devices.
        plant_sensors_entries = entity_registry.async_entries_for_device(entity_reg, i.id)

        # entries_str = [
        #     entry.entity_id
        #     for entry in plant_sensors_entries
        #     if entry.domain == 'sensor' and entry.original_device_class in OPB_MEASUREMENTS_TO_UPLOAD
        # ]
        #
        # sensor_entity_states = await hass.async_add_executor_job(
        #     get_significant_states, hass, query_period_start_timestamp, query_period_end_timestamp, entries_str
        # )

        # It's hard to get to the PID for Plantbook so getting it via Plant-Device's entity_id and its states
        plant_device_state = None
        plant_entity_id = None
        for entry in plant_sensors_entries:
            if entry.domain == 'plant':
                plant_entity_id = entry.entity_id

                # Get OPB component's config state
                plant_device_state = await get_instance(hass).async_add_executor_job(
                    get_last_state_changes, hass, 1,
                    plant_entity_id
                )
                break

        if not plant_device_state or not plant_entity_id:
            _LOGGER.error(
                "Unable to query because Config-state is not found for Plant-device %s - %s" % (i.name, i.model))
            continue

        # Corresponding PID(Plant_ID)
        opb_pid = plant_device_state[plant_entity_id][0].attributes['species_original']

        # Plant-instance ID
        plant_instance_id = i.id

        # Register Plant-instance
        reg_map = {plant_instance_id: opb_pid}
        _LOGGER.debug("Registering Plant-instance: %s" % str(reg_map))
        try:
            res = await hass.data[DOMAIN][ATTR_API].async_plant_instance_register(sensor_pid_map=reg_map,
                                                                                  location_country=location.get(
                                                                                      'country'),
                                                                                  location_lon=location.get('lon'),
                                                                                  location_lat=location.get('lat'))
        except Exception as ex:
            _LOGGER.error("Unable to register Plant-instance: %s due to Exception: %s" % (str(reg_map), ex))
            continue

        _LOGGER.debug("Registration response: %s" % str(res))
        # Error out if unexpected response has been received
        try:
            # Get OpenPlantbook generated ID for the Plant-instance
            custom_id = res[0]['id']
        except:
            _LOGGER.error("Unexpected API response: %s" % res)
            continue

        # Get the latest_data timestamp from OPB response
        latest_data = res[0].get('latest_data')
        _LOGGER.debug("Latest_data timestamp from OPB (in UTC): %s" % str(latest_data))

        query_period_end_timestamp = dt_util.now(dt.UTC)

        if latest_data:
            query_period_start_timestamp = dt_util.parse_datetime(latest_data).astimezone(dt.UTC)

            # If last upload was more than 7 days ago then only take last 7 days
            if query_period_end_timestamp - query_period_start_timestamp > timedelta(days=7):
                query_period_start_timestamp = query_period_end_timestamp - timedelta(days=7)
        else:
            # First time upload for the sensor as no latest_data in the response. Taking only last day of data
            query_period_start_timestamp = query_period_end_timestamp - timedelta(days=1)

        _LOGGER.debug("Querying plant-sensors data from %s to %s" % (
        dt_util.as_local(query_period_start_timestamp), dt_util.as_local(query_period_end_timestamp)))

        # Create time_series for each measurement of the same "plant_id"
        measurements = {
            'temperature': TimeSeries(identifier=custom_id, name="temp"),
            'moisture': TimeSeries(identifier=custom_id, name="soil_moist"),
            'conductivity': TimeSeries(identifier=custom_id, name="soil_ec"),
            'illuminance': TimeSeries(identifier=custom_id, name="light_lux"),
            'humidity': TimeSeries(identifier=custom_id, name="air_humid")
        }

        # Go through sensors entries
        for entry in plant_sensors_entries:
            # process supported measurements of the sensor
            if entry.domain == 'sensor' and entry.original_device_class in OPB_MEASUREMENTS_TO_UPLOAD:
                # Get sensors states (history) over the period of time
                sensor_entity_states = await get_instance(hass).async_add_executor_job(
                    get_significant_states, hass, query_period_start_timestamp, query_period_end_timestamp,
                    [entry.entity_id]
                )
                # state_changes_during_period = await get_instance(hass).async_add_executor_job(
                #         get_significant_states, hass, query_period_start_timestamp, query_period_end_timestamp,
                #         [entry.entity_id]
                # )

                _LOGGER.debug("Parsing states of: %s " % entry)
                # Convert HASS state to JTS time_series excluding 'unknown' states
                for entity_states in sensor_entity_states.values():
                    for state in entity_states:
                        # check if it is meaningful state
                        if state.state == 'unknown' or state.state == 'unavailable':
                            continue
                        # check if we are getting the last value of the state which was not updated over query period
                        if dt_util.as_utc(state.last_updated) == dt_util.as_utc(query_period_start_timestamp):
                            # This is last state without updates - skip it
                            continue

                        try:
                            float(state.state)
                        except:
                            continue


                        # Add a state to TimeSeries
                        measurements[entry.original_device_class].insert(
                            TsRecord(dt_util.as_local(state.last_updated), state.state))
                        _LOGGER.debug("Added Time-Series: %s %s" % (dt_util.as_local(state.last_updated), state.state))

        # Remove empty measurements
        for m in measurements.values():
            if len(m) != 0:
                jts_doc.addSeries(m)

    if len(jts_doc) > 0:
        _LOGGER.debug("An upload payload: %s" % jts_doc.toJSONString())
        res = await hass.data[DOMAIN][ATTR_API].async_plant_data_upload(jts_doc, dry_run=False)
        _LOGGER.info("Uploading data from %s sensors was %s" % (len(jts_doc), "successful" if res else "failure"))
        return {'result': res}
    else:
        _LOGGER.info("Nothing to upload")
        return None

async def async_setup_upload_schedule(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the time sync."""
    # TODO V: Check if sensor upload is enabled

    _LOGGER.debug("Setting up plant-sensors upload schedule")

    async def upload_data(now: datetime) -> None:
        # now = dt_util.as_local(now)
        _LOGGER.info("Plant-sensors data upload initiated")
        await plant_data_upload(hass, entry)

    # Check if upload is enabled via OptionFlow
    upload_sensors = entry.options.get(FLOW_UPLOAD_DATA)

    if upload_sensors:

        _LOGGER.info("Plant-sensors data upload schedule is active")

        @callback
        def start_schedule(_event: Event) -> None:
            """Start the send schedule after the started event."""
            # Wait UPLOAD_WAIT_AFTER_RESTART min after started to upload 1st batch
            async_call_later(
                hass,
                UPLOAD_WAIT_AFTER_RESTART,
                HassJob(
                    upload_data,
                    name="opb sensors upload schedule after start",
                    cancel_on_shutdown=True,
                ),
            )

            # Upload on UPLOAD_TIME_INTERVAL interval
            remove_upload_listener = async_track_time_interval(
                hass,
                upload_data,
                UPLOAD_TIME_INTERVAL,
                name="opb sensors upload daily",
                cancel_on_shutdown=True,
            )
            hass.data[DOMAIN]['remove_upload_listener'] = remove_upload_listener
            entry.async_on_unload(remove_upload_listener)

        start_schedule(None)
        # hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_schedule)

        # remove_upload_listener = async_track_time_interval(hass, upload_data, UPLOAD_TIME_INTERVAL)
        # await upload_data(dt_util.utcnow())

    else:
        _LOGGER.info("Plant-sensors data upload schedule is disabled")

        if hass.data[DOMAIN].get('remove_upload_listener'):
            hass.data[DOMAIN]['remove_upload_listener']()
            hass.data[DOMAIN]['remove_upload_listener'] = None

# class Plant_data_uploader:
#
#     def __init__(self, hass: HomeAssistant) -> None:
#         """Initialize the heartbeat."""
#         self._hass = hass
#         self._unsubscribe: CALLBACK_TYPE | None = None
#
#     async def async_setup(self) -> None:
#         """Set up the heartbeat."""
#         if self._unsubscribe is None:
#             await self.async_heartbeat(dt.datetime.now())
#             self._unsubscribe = event.async_track_time_interval(
#                 self._hass, self.async_heartbeat, self.HEARTBEAT_INTERVAL
#             )
#
#     async def async_unload(self) -> None:
#         """Unload the heartbeat."""
#         if self._unsubscribe is not None:
#             self._unsubscribe()
#             self._unsubscribe = None
