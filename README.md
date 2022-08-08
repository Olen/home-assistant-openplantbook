# OpenPlantbook integration for Home Assistant

This integration does not do much by itself.  What it does is create two service calls so Home Assistant can search and get data from the [OpenPlantbook API](https://open.plantbook.io/).

This is used as a base for the sister-integration https://github.com/Olen/homeassistant-plant which utilizes this API to add threshold values for such as moisture, temperature, condictivity etc. based on the plant speices.


## Installation
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

This can be installed manually or through HACS
### Via HACS
* Add this repo as a "Custom repository" with type "Integration"
  * Click HACS in your Home Assistnat
  * Click Integrations
  * Click the 3 dots in the top right corner and select "Custom Repositories"
  * Add the URL to this github repository and category "Integration"
* Click "Install" in the new "OpenPlantbook" card in HACS.
* Wait for install to complete
* Restart Home Assistant

### Manual Installation
* Copy the whole`custom_components/openplantbook/` directory to your server's `<config>/custom_components` directory
* Restart Home Assistant


## Configuration

The integration is set up using the GUI.  You must have a valid `client_id` and `secret` from OpenPlantbook to set up the integration.
After creating an account at the OpenPlantbook, you can find your `client_id` and `secret` here: https://open.plantbook.io/apikey/show/

Go to "Settings" -> "Integrations" in Home Assistant.  Click "Add integration" and find "OpenPlantbook" in the list.

## Examples

Two service calls are added by this integration:

`openplantbook.search` searches the API for plants matching a string. The search result is added to the entity `openplantbook.search_result` with the number of returned results as the `state` and a list of results in the state attributes.

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


`openplantbook.get` gets detailed data for a single plant. The result is added to the entity `openplantbook.<species name>` with parameters for different max/min values set as attributes.  

>**info**
>
> You need to search for the exact string returned as "pid" in `openplantbook.search_result` to get the right plant.


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
