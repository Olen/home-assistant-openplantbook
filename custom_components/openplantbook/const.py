"""Constants for the openplantbook integration."""

from typing import Final

DOMAIN: Final[str] = "openplantbook"
PLANTBOOK_BASEURL: Final[str] = "https://open.plantbook.io/api/v1"
ATTR_ALIAS: Final[str] = "alias"
ATTR_PLANT_INSTANCE: Final[str] = "plant_instance"
ATTR_SPECIES: Final[str] = "species"
ATTR_API: Final[str] = "api"
ATTR_HOURS: Final[str] = "hours"
ATTR_IMAGE: Final[str] = "image_url"
CACHE_TIME: Final[int] = 24

OPB_ATTR_SEARCH: Final[str] = "search"
OPB_ATTR_SEARCH_RESULT: Final[str] = "search_result"
OPB_ATTR_RESULT: Final[str] = "result"
OPB_ATTR_RESULTS: Final[str] = "results"
OPB_ATTR_TIMESTAMP: Final[str] = "timestamp"

OPB_SERVICE_SEARCH: Final[str] = "search"
OPB_SERVICE_GET: Final[str] = "get"
OPB_SERVICE_UPLOAD: Final[str] = "upload"
OPB_SERVICE_CLEAN_CACHE: Final[str] = "clean_cache"

OPB_PID: Final[str] = "pid"
OPB_DISPLAY_PID: Final[str] = "display_pid"

FLOW_DOWNLOAD_IMAGES: Final[str] = "download_images"
FLOW_DOWNLOAD_PATH: Final[str] = "download_path"
DEFAULT_IMAGE_PATH: Final[str] = "/config/www/images/plants/"

OPB_MEASUREMENTS_TO_UPLOAD = [
    "moisture",
    "illuminance",
    "conductivity",
    "temperature",
    "humidity",
]
OPB_INFO_MESSAGE: Final[str] = "info_message"
OPB_CURRENT_INFO_MESSAGE: Final[int] = 1
FLOW_UPLOAD_DATA: Final[str] = "upload_data"
FLOW_UPLOAD_HASS_LOCATION_COUNTRY: Final[str] = "upload_data_hass_location_country"
FLOW_UPLOAD_HASS_LOCATION_COORD: Final[str] = "upload_data_hass_location_coordinates"
