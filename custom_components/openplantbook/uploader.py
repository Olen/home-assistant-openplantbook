from datetime import timedelta, datetime
from typing import Any

from json_timeseries import JtsDocument, TsRecord, TimeSeries
from openplantbook_sdk import ValidationError

import homeassistant.util.dt as dt_util
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import (
    get_significant_states,
    get_last_state_changes,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, Event, HassJob
from homeassistant.helpers import device_registry
from homeassistant.helpers import entity_registry
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.util import dt
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfConductivity,
    LIGHT_LUX,
    PERCENTAGE,
)
from .plantbook_exception import OpenPlantbookException
from .const import (
    DOMAIN,
    OPB_MEASUREMENTS_TO_UPLOAD,
    ATTR_API,
    FLOW_UPLOAD_DATA,
    FLOW_UPLOAD_HASS_LOCATION_COUNTRY,
    FLOW_UPLOAD_HASS_LOCATION_COORD,
)
import logging

UPLOAD_TIME_INTERVAL = timedelta(days=1)
UPLOAD_WAIT_AFTER_RESTART = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


# Take HASS state and verify if it is sane and supported by OPB and convert if necessary
def get_supported_state_value(state) -> tuple:
    def validate_measurement(supported_unit, value_range):
        nonlocal state_error

        if unit_of_measurement != supported_unit:
            _LOGGER.debug(
                "Unit '%s' of '%s' measurement is not supported. Its value '%s' disregarded"
                % (unit_of_measurement, current_measurement, supported_state)
            )
            state_error = current_measurement

        elif supported_state < value_range[0] or supported_state > value_range[1]:
            _LOGGER.debug(
                "Value '%s' of %s is out of range %s - disregarded"
                % (supported_state, current_measurement, value_range)
            )
            state_error = current_measurement

        return

    current_measurement = state.attributes.get("device_class")
    unit_of_measurement = state.attributes.get("unit_of_measurement")
    state_error = None

    try:
        supported_state = round(float(state.state))
    except:
        _LOGGER.debug(
            "State is not a number - disregarded: state_value: '%s', state: %s"
            % (state.state, state)
        )
        return None, current_measurement

    # temperature
    if current_measurement == "temperature":

        # Convert Fahrenheit to Celsius
        if unit_of_measurement == UnitOfTemperature.FAHRENHEIT:
            supported_state = round((supported_state - 32) * 5 / 9)
            _LOGGER.debug(
                "Temperature converted from %s °F to %s °C"
                % (state.state, supported_state)
            )
            unit_of_measurement = UnitOfTemperature.CELSIUS

        # Convert Kelvin to Celsius
        elif unit_of_measurement == UnitOfTemperature.KELVIN:
            supported_state = round(supported_state - 273.15)
            _LOGGER.debug(
                "Temperature converted from %s K to %s °C"
                % (state.state, supported_state)
            )
            unit_of_measurement = UnitOfTemperature.CELSIUS

        validate_measurement("°C", (-50, 70))

    # humidity
    elif current_measurement == "humidity":
        validate_measurement(PERCENTAGE, (0, 100))

    # illuminance
    elif current_measurement == "illuminance":
        validate_measurement(LIGHT_LUX, (0, 200000))

    # moisture
    elif current_measurement == "moisture":
        validate_measurement(PERCENTAGE, (0, 100))

    # conductivity
    elif current_measurement == "conductivity":
        validate_measurement(UnitOfConductivity.MICROSIEMENS_PER_CM, (0, 3000))

    # unsupported device_class
    else:
        _LOGGER.debug("Unsupported device_class: %s" % state)
        state_error = "device_class"

    return supported_state, state_error


async def plant_data_upload(hass, entry, call=None) -> dict[str, Any] | None:
    if DOMAIN not in hass.data:
        raise OpenPlantbookException("no data found for domain %s", DOMAIN)
    # _device_id = call.data.get(ATTR_PLANT_INSTANCE)

    if call:
        _LOGGER.info("Plant-sensors data upload service is triggered")

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
        if "plant" in str(d.identifiers) and d.name_by_user is None:
            plant_devices.append(d)

    entity_reg = entity_registry.async_get(hass)
    jts_doc = JtsDocument()

    # Go through plant devices one by one and extract corresponding sensors' states
    for i in plant_devices:
        # Get entity ids for plant devices.
        plant_sensors_entries = entity_registry.async_entries_for_device(
            entity_reg, i.id
        )

        # It's hard to get to the PID for Plantbook so getting it via Plant-Device's entity_id and its states
        plant_device_state = None
        plant_entity_id = None
        for entry in plant_sensors_entries:
            if entry.domain == "plant":
                plant_entity_id = entry.entity_id

                # Get OPB component's config state
                plant_device_state = await get_instance(hass).async_add_executor_job(
                    get_last_state_changes, hass, 1, plant_entity_id
                )
                break

        if not plant_device_state or not plant_entity_id:
            _LOGGER.error(
                "Unable to query because Config-state is not found for Plant-device %s - %s"
                % (i.name, i.model)
            )
            continue

        # Corresponding PID(Plant_ID)
        _LOGGER.debug("Plant_device_state: %s" % (plant_device_state))
        opb_pid = plant_device_state[plant_entity_id][0].attributes["species_original"]

        # Plant-instance ID
        plant_instance_id = i.id

        # Registering Plant-instance
        reg_map = {plant_instance_id: opb_pid}
        _LOGGER.debug("Registering Plant-instance: %s" % str(reg_map))

        res = None
        caught_exception = None
        try:
            res = await hass.data[DOMAIN][ATTR_API].async_plant_instance_register(
                sensor_pid_map=reg_map,
                location_country=location.get("country"),
                location_lon=location.get("lon"),
                location_lat=location.get("lat"),
            )

        # OPB ValidationFailure
        except ValidationError as ex:

            caught_exception = ex
            opb_errors = ex.errors

            if opb_errors[0]["code"] == "invalid_pid":

                # workaround for case when HASS original_species is set to DISPLAY_PID rather than PID attempt to find
                # the plant using PID as DISPLAY_PID and if found only 1 plant and DISPLAY_PID match they retry
                try:
                    search_res = await hass.data[DOMAIN][ATTR_API].async_plant_search(
                        search_text=opb_pid
                    )

                    if search_res["count"] == 1:

                        if opb_pid == search_res["results"][0]["display_pid"]:
                            opb_disp_pid = opb_pid
                            opb_pid = search_res["results"][0]["pid"]
                            reg_map[plant_instance_id] = opb_pid

                            res = await hass.data[DOMAIN][
                                ATTR_API
                            ].async_plant_instance_register(
                                sensor_pid_map=reg_map,
                                location_country=location.get("country"),
                                location_lon=location.get("lon"),
                                location_lat=location.get("lat"),
                            )

                            _LOGGER.debug(
                                "The workaround found match between display_pid '%s' and pid: '%s'. The "
                                "Plant-instance has been registered with %s"
                                % (opb_disp_pid, opb_pid, opb_pid)
                            )
                            caught_exception = None

                except Exception as ex_in:
                    _LOGGER.debug(
                        "The 'display_pid workaround' failed to register Plant-instance: %s due to Exception: %s"
                        % (str(reg_map), ex_in)
                    )

        except Exception as ex:
            caught_exception = ex

        if caught_exception:
            _LOGGER.error(
                "Cannot upload sensor data for plant '%s' because Unable to register Plant-instance due to Exception: %s"
                % (str(reg_map), caught_exception)
            )
            continue

        _LOGGER.debug("Registration is successful with response: %s" % str(res))
        # Error out if unexpected response has been received
        try:
            # Get OpenPlantbook generated ID for the Plant-instance
            custom_id = res[0]["id"]
        except:
            _LOGGER.error("Cannot parse API response: %s" % res)
            continue

        # Get the latest_data timestamp from OPB response
        latest_data = res[0].get("latest_data")
        _LOGGER.debug("Latest_data timestamp from OPB (in UTC): %s" % str(latest_data))

        query_period_end_timestamp = dt_util.now(dt.UTC)

        if latest_data:
            query_period_start_timestamp = dt_util.parse_datetime(
                latest_data
            ).astimezone(dt.UTC) + timedelta(seconds=1)

            # If last upload was more than 7 days ago then only take last 7 days
            if query_period_end_timestamp - query_period_start_timestamp > timedelta(
                days=7
            ):
                query_period_start_timestamp = query_period_end_timestamp - timedelta(
                    days=7
                )
        else:
            # First time upload for the sensor as no latest_data in the response. Taking only last day of data
            query_period_start_timestamp = query_period_end_timestamp - timedelta(
                days=1
            )

        _LOGGER.debug(
            "Querying plant-sensors data from %s to %s"
            % (
                dt_util.as_local(query_period_start_timestamp),
                dt_util.as_local(query_period_end_timestamp),
            )
        )

        # Create time_series for each measurement of the same "plant_id"
        measurements = {
            "temperature": TimeSeries(identifier=custom_id, name="temp"),
            "moisture": TimeSeries(identifier=custom_id, name="soil_moist"),
            "conductivity": TimeSeries(identifier=custom_id, name="soil_ec"),
            "illuminance": TimeSeries(identifier=custom_id, name="light_lux"),
            "humidity": TimeSeries(identifier=custom_id, name="env_humid"),
        }

        # Go through sensors entries
        for entry in plant_sensors_entries:
            # process supported measurements of the sensor
            if (
                entry.domain == "sensor"
                and entry.original_device_class in OPB_MEASUREMENTS_TO_UPLOAD
            ):
                # Get sensors states (history) over the period of time
                sensor_entity_states = await get_instance(hass).async_add_executor_job(
                    get_significant_states,
                    hass,
                    query_period_start_timestamp,
                    query_period_end_timestamp,
                    [entry.entity_id],
                )

                _LOGGER.debug("Parsing states of: %s " % entry)

                measurement_errors = []

                # Convert HASS state to JTS time_series excluding 'unknown' states
                for entity_states in sensor_entity_states.values():

                    for state in entity_states:
                        # check if it is meaningful state
                        if state.state == "unknown" or state.state == "unavailable":
                            continue
                        # check if we are getting the last value of the state which was not updated over query period
                        if dt_util.as_utc(state.last_updated) == dt_util.as_utc(
                            query_period_start_timestamp
                        ):
                            # This is last state without updates - skip it
                            continue

                        # Get supported state value
                        supported_state_value, state_error = get_supported_state_value(
                            state
                        )

                        if state_error:
                            # _LOGGER.debug(
                            #     "State value error detected: state_error - %s, state - %s"
                            #     % (state_error, state)
                            # )
                            if state_error not in measurement_errors:
                                measurement_errors.append(state_error)
                            continue

                        # Add a state to TimeSeries
                        measurements[entry.original_device_class].insert(
                            TsRecord(
                                dt_util.as_local(state.last_updated),
                                supported_state_value,
                            )
                        )
                        _LOGGER.debug(
                            "Added Time-Series Record: %s %s"
                            % (
                                dt_util.as_local(state.last_updated),
                                supported_state_value,
                            )
                        )

                if measurement_errors:
                    _LOGGER.info(
                        "Plant (Entity) %s has errors in measurements: %s. The invalid values were disregarded. You may"
                        "enable debug logging for more information."
                        % (entry, measurement_errors)
                    )

        # Remove empty measurements
        for m in measurements.values():
            if len(m) != 0:
                jts_doc.addSeries(m)

    if len(jts_doc) > 0:
        _LOGGER.debug("Payload to upload: %s" % jts_doc.toJSONString())
        _LOGGER.debug("Calling OPB SDK to upload data")
        res = await hass.data[DOMAIN][ATTR_API].async_plant_data_upload(
            jts_doc, dry_run=False
        )
        _LOGGER.info(
            "Uploading data from %s sensors was %s"
            % (len(jts_doc), "successful" if res else "failure")
        )
        return {"result": res}
    else:
        _LOGGER.info("Found no sensors data to upload")

        if latest_data:
            days_since_upload = dt_util.now(dt.UTC) - dt_util.parse_datetime(
                latest_data
            ).astimezone(dt.UTC)
            if (days_since_upload.days > 3) and dt_util.now(dt.UTC).weekday() == 4:
                _LOGGER.warning(
                    "The last time plant sensors data was successfully uploaded %s days ago. This may indicate a "
                    "problem with Plants sensors or this integration. Please enable OpenPlantbook integration's debug "
                    "logging for more information. "
                    "You may report this issue via GitHub or support@plantbook.io attaching the debug log if you "
                    "believe it is a bug." % days_since_upload.days
                )
        else:
            # no latest_data in the OPB API indicates that the data has never been uploaded successfully for the plant
            if dt_util.now(dt.UTC).weekday() == 6:
                _LOGGER.warning(
                    "Plants sensors data has never been uploaded successfully. This may indicate a problem with the sensors "
                    "or this integration. Please enable OpenPlantbook integration's debug logging for more information. "
                    "You may report this issue via GitHub or support@plantbook.io attaching the debug log if you "
                    "believe it is a bug."
                )

        return None


async def async_setup_upload_schedule(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the time sync."""

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
            hass.data[DOMAIN]["remove_upload_listener"] = remove_upload_listener
            entry.async_on_unload(remove_upload_listener)

        start_schedule(None)
        # hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_schedule)

    else:
        _LOGGER.info("Plant-sensors data upload schedule is disabled")

        if hass.data[DOMAIN].get("remove_upload_listener"):
            hass.data[DOMAIN]["remove_upload_listener"]()
            hass.data[DOMAIN]["remove_upload_listener"] = None


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
