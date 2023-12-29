# OpenPlantbook integration for Home Assistant

This integration allows fetching plants information from and uploading plant sensors' data to OpenPlantBook.
It creates a few service calls in Home Assistant to interact with [OpenPlantbook API](https://open.plantbook.io/) which
are:

* Search plant
* Get plant details
* Upload plants sensors data

This is used as a base for the sister-integration https://github.com/Olen/homeassistant-plant which utilizes this API to
add threshold values for such as moisture, temperature, conductivity etc. based on the plant species.

## Installation

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

This can be installed manually or through HACS

### Via HACS

* Add this repo as a "Custom repository" with type "Integration"
    * Click HACS in your Home Assistant
    * Click Integrations
    * Click the 3 dots in the top right corner and select "Custom Repositories"
    * Add the URL to this GitHub repository and category "Integration"
* Click "Install" in the new "OpenPlantbook" card in HACS.
* Wait for install to complete
* Restart Home Assistant

### Manual Installation

* Copy the whole`custom_components/openplantbook/` directory to your server's `<config>/custom_components` directory
* Restart Home Assistant

## Set up

The integration is set up using the GUI. You must have a valid `client_id` and `secret` from OpenPlantbook to set up the
integration.
After creating an account at the OpenPlantbook, you can find your `client_id` and `secret`
here: https://open.plantbook.io/apikey/show/

Go to "Settings" -> "Integrations" in Home Assistant. Click "Add integration" and find "OpenPlantbook" in the list.
The integration validates the credentials and throws an error if they are incorrect.

## Configuration

The integration provide the following configuration options:

![image](./images/config-options.png)

### Upload plant-sensors' data

>**NOTE:** All the data is shared anonymously.

This option will enable the integration to look for plants created with
sister-integration https://github.com/Olen/homeassistant-plant Then it will periodically (once a day) upload
corresponding sensors' data to OpenPlantbook.

This allows Plantbook users to browse this data and to create a useful dataset. More information about this feature can
be found: https://open.plantbook.io/ui/sensor-data/

First time the component uploads data for last 24 hours. If sensors' data
is not available for some reason over period of time (sensors are not connected), the component will try to upload
data (once a day)
for period up to last 7 days. E.g.: Sensors are disconnected for 2 days, then the component will query the data
since last successful upload but up to 7 days. Once data is available, it will be uploaded.

The upload can be triggered manually using the service. See examples below.

### Share location to complement sensors' data

This option will allow the integration to share Home Assistant location to compliment sensors' data. This allows to
better understand the environment where a plant grows. The location sharing is only applicable when uploading is
enabled.

There are 2 options to share location:

1. Share only country from Home Assistant configuration.
2. Share location coordinates from Home Assistant configuration.

Location can be set in Home Assistant under Settings/System/General as on screenshot below:

![image](.\images\hass-location.png)

It'd be great if you could share at least a country.

>**NOTE**: You can enable DEBUG logging for the integration to see what is being shared.

![image](.\images\debug-logging.png)

### Automatically download images from OpenPlantbook.

The default path to save the images is `/config/www/images/plants`, but it can be set to any directory you wish.

You need to specify an _existing path_ that the user you are running home assistant as has write access to. If you
specify a relative path (e.g. a path that does not start with a "/", it means a path below your "config" directory. So "
www/images/plants" will mean "&lt;home-assistant-install-directory&gt;/config/www/images/plants".

If the path contains **"www/"** the image_url in plant attributes will also be replaced by a reference to
/local/<path to image>. So if the download path is set to the default "/config/www/images/plants/", the "image_url" of
the species will be replaced with "/local/images/plants/my plant species.jpg".

If the path does _not_ contain **"www/"** the full link to the image in OpenPlantbook is kept as it is, but the image is
still downloaded to the path you specify.

Existing files will never be overwritten, and the path needs to exist before the integration is configured.

## Examples

Service calls are added by this integration:

### openplantbook.upload

`openplantbook.upload` can be used to manually trigger uploading of plant-sensors data to OpenPlantbook. No parameters required.

```yaml
service: openplantbook.upload
```

Service return "null" if nothing was uploaded or there was an error. The details can be found in Home Assistant log.

### openplantbook.search

`openplantbook.search` searches the API for plants matching a string. The search result is added to the
entity `openplantbook.search_result` with the number of returned results as the `state` and a list of results in the
state attributes.

```yaml
service: openplantbook.search
service_data:
  alias: Capsicum
```

The result can then be read back from the `openplantbook.search_result` once the search completes:

```jinja2
Number of plants found: {{ states('openplantbook.search_result') }}
{%- for pid in states.openplantbook.search_result.attributes %}
  {%- set name = state_attr('openplantbook.search_result', pid) %}
  * {{pid}} -> {{name}}
{%- endfor %}
```

Which would produce

Number of plants found: 40

* capsicum annuum -> Capsicum annuum
* capsicum baccatum -> Capsicum baccatum
* capsicum bomba yellow red -> Capsicum Bomba yellow red
* capsicum chinense -> Capsicum chinense
  (...)

### openplantbook.get

`openplantbook.get` gets detailed data for a single plant. The result is added to the
entity `openplantbook.<species name>` with parameters for different max/min values set as attributes.

>**NOTE:** You need to search for the exact string returned as "pid" in `openplantbook.search_result` to get the right plant.

```yaml
service: openplantbook.get
service_data:
  species: capsicum annuum
```

And the results can be found in `openplantbook.capsicum_annuum`:

```jinja2
Details for plant {{ states('openplantbook.capsicum_annuum') }}
* Max moisture: {{ state_attr('openplantbook.capsicum_annuum', 'max_soil_moist') }}
* Min moisture: {{ state_attr('openplantbook.capsicum_annuum', 'min_soil_moist') }}
* Max temperature: {{ state_attr('openplantbook.capsicum_annuum', 'max_temp') }}
* Image: {{ state_attr('openplantbook.capsicum_annuum', 'image_url') }}
```

Which gives

Details for plant Capsicum annuum

* Max moisture: 65
* Min moisture: 20
* Max temperature: 35
* Min temperature: 15
* (...)
* Image: https://.../capsicum%20annuum.jpg

### Quick UI example

Just to show how the service calls can be utilized to search the OpenPlantbook API

![Example](images/openplantbook.gif)

**PS!**

This UI is _not_ part of the integration. It is just an example of how to use the service calls.

An explanation of the UI is available
here: https://github.com/Olen/home-assistant-openplantbook/blob/main/examples/GUI.md

<a href="https://www.buymeacoffee.com/olatho" target="_blank">
<img src="https://user-images.githubusercontent.com/203184/184674974-db7b9e53-8c5a-40a0-bf71-c01311b36b0a.png" style="height: 50px !important;"> 
</a>
