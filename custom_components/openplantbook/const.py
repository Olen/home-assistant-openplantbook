"""Constants for the openplantbook integration."""

DOMAIN = "openplantbook"
PLANTBOOK_BASEURL = "https://open.plantbook.io/api/v1"
ATTR_ALIAS = "alias"
ATTR_PLANT_INSTANCE = "plant_instance"
ATTR_SPECIES = "species"
ATTR_API = "api"
ATTR_HOURS = "hours"
ATTR_IMAGE = "image_url"
CACHE_TIME = 24

OPB_ATTR_SEARCH = "search"
OPB_ATTR_SEARCH_RESULT = "search_result"
OPB_ATTR_RESULT = "result"
OPB_ATTR_RESULTS = "results"
OPB_ATTR_TIMESTAMP = "timestamp"

OPB_SERVICE_SEARCH = "search"
OPB_SERVICE_GET = "get"
OPB_SERVICE_UPLOAD = "upload"
OPB_SERVICE_CLEAN_CACHE = "clean_cache"

OPB_PID = "pid"
OPB_DISPLAY_PID = "display_pid"

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
OPB_INFO_MESSAGE = "info_message"
OPB_CURRENT_INFO_MESSAGE = 1
FLOW_UPLOAD_DATA = "upload_data"
FLOW_UPLOAD_HASS_LOCATION_COUNTRY = "upload_data_hass_location_country"
FLOW_UPLOAD_HASS_LOCATION_COORD = "upload_data_hass_location_coordinates"
