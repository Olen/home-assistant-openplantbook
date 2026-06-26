"""Constants for the openplantbook integration."""

DOMAIN = "openplantbook"
PLANTBOOK_BASEURL = "https://open.plantbook.io/api/v1"
ATTR_ALIAS = "alias"
ATTR_PLANT_INSTANCE = "plant_instance"
ATTR_SPECIES = "species"
ATTR_API = "api"

# hass.data[DOMAIN] keys for the entity layer
DATA_COMPONENT = "component"
DATA_SEARCH_ENTITY = "search_entity"
DATA_SPECIES_ENTITIES = "species_entities"
ATTR_HOURS = "hours"
ATTR_INCLUDE = "include"
ATTR_IMAGE = "image_url"
CACHE_TIME = 24

OPB_ATTR_SEARCH = "search"
OPB_ATTR_SEARCH_RESULT = "search_result"
OPB_ATTR_RESULT = "result"
OPB_ATTR_RESULTS = "results"
OPB_ATTR_TIMESTAMP = "timestamp"
# Internal marker stored on a cached plant_data dict: the list of extra
# `include` categories that the cached entry already satisfies (e.g. ["care"]).
OPB_ATTR_INCLUDES = "_fetched_includes"

OPB_SERVICE_SEARCH = "search"
OPB_SERVICE_GET = "get"
OPB_SERVICE_UPLOAD = "upload"
OPB_SERVICE_CLEAN_CACHE = "clean_cache"

OPB_PID = "pid"
OPB_DISPLAY_PID = "display_pid"
OPB_MAX_LIGHT_MMOL = "max_light_mmol"
OPB_MIN_LIGHT_MMOL = "min_light_mmol"
OPB_MAX_LIGHT_LUX = "max_light_lux"
OPB_MAX_DLI = "max_dli"
OPB_MIN_DLI = "min_dli"

FLOW_DOWNLOAD_IMAGES = "download_images"
FLOW_DOWNLOAD_PATH = "download_path"
DEFAULT_IMAGE_PATH = "/config/www/images/plants/"

OPB_MEASUREMENTS_TO_UPLOAD = [
    "moisture",
    "illuminance",
    "conductivity",
    "temperature",
    "humidity",
]
FLOW_UPLOAD_DATA = "upload_data"
FLOW_UPLOAD_HASS_LOCATION_COUNTRY = "upload_data_hass_location_country"
FLOW_UPLOAD_HASS_LOCATION_COORD = "upload_data_hass_location_coordinates"
# New option: control whether to send Home Assistant language to OpenPlantbook API
FLOW_SEND_LANG = "use_ha_language"

# DLI conversion: OpenPlantbook mmol light values are daily integrals
# (mmol/m²/d), so DLI (mol/m²/d) is a plain millimole→mole unit conversion.
MMOL_TO_DLI_FACTOR = 0.001

# Physical ceiling for DLI (mol/m²/d): ~65 is the maximum daily light integral
# attainable at Earth's surface (full tropical sun, clear sky, long day).
# OpenPlantbook aggregates loosely validated, multi-source data; a converted
# value above this is biologically impossible and signals suspect data, so it
# is clamped. No lower guard: legitimate deep-shade minimums round toward 0.
DLI_SANITY_MAX = 65.0
