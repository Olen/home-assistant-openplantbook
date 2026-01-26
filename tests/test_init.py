# # """Test component setup."""
# from homeassistant.setup import async_setup_component
#
# from custom_components.openplantbook.const import DOMAIN
#
#
# async def test_async_setup(hass):
#     """Test the component gets setup."""
#     assert await async_setup_component(hass, DOMAIN, {}) is True
#
#

import pytest
from unittest.mock import Mock

from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfConductivity,
    UnitOfTemperature,
)

from custom_components.openplantbook.uploader import get_supported_state_value


@pytest.mark.parametrize(
    "state, expected_value, expected_error",
    [
        # Test temperature in Fahrenheit
        (
            Mock(
                state="77",
                attributes={
                    "device_class": "temperature",
                    "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                },
            ),
            25,
            None,
        ),
        # Test temperature in Kelvin
        (
            Mock(
                state="300",
                attributes={
                    "device_class": "temperature",
                    "unit_of_measurement": UnitOfTemperature.KELVIN,
                },
            ),
            27,
            None,
        ),
        # Test temperature out of range
        (
            Mock(
                state="200",
                attributes={
                    "device_class": "temperature",
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                },
            ),
            200,
            "temperature",
        ),
        # Test unsupported temperature unit
        (
            Mock(
                state="25",
                attributes={
                    "device_class": "temperature",
                    "unit_of_measurement": "unknown",
                },
            ),
            25,
            "temperature",
        ),
        # Test humidity
        (
            Mock(
                state="50",
                attributes={
                    "device_class": "humidity",
                    "unit_of_measurement": PERCENTAGE,
                },
            ),
            50,
            None,
        ),
        # Test humidity out of range
        (
            Mock(
                state="150",
                attributes={
                    "device_class": "humidity",
                    "unit_of_measurement": PERCENTAGE,
                },
            ),
            150,
            "humidity",
        ),
        # Test unsupported humidity unit
        (
            Mock(
                state="50",
                attributes={
                    "device_class": "humidity",
                    "unit_of_measurement": "unknown",
                },
            ),
            50,
            "humidity",
        ),
        # Test illuminance
        (
            Mock(
                state="1000",
                attributes={
                    "device_class": "illuminance",
                    "unit_of_measurement": LIGHT_LUX,
                },
            ),
            1000,
            None,
        ),
        # Test illuminance out of range
        (
            Mock(
                state="300000",
                attributes={
                    "device_class": "illuminance",
                    "unit_of_measurement": LIGHT_LUX,
                },
            ),
            300000,
            "illuminance",
        ),
        # Test unsupported illuminance unit
        (
            Mock(
                state="1000",
                attributes={
                    "device_class": "illuminance",
                    "unit_of_measurement": "unknown",
                },
            ),
            1000,
            "illuminance",
        ),
        # Test moisture
        (
            Mock(
                state="30",
                attributes={
                    "device_class": "moisture",
                    "unit_of_measurement": PERCENTAGE,
                },
            ),
            30,
            None,
        ),
        # Test moisture out of range
        (
            Mock(
                state="150",
                attributes={
                    "device_class": "moisture",
                    "unit_of_measurement": PERCENTAGE,
                },
            ),
            150,
            "moisture",
        ),
        # Test unsupported moisture unit
        (
            Mock(
                state="30",
                attributes={
                    "device_class": "moisture",
                    "unit_of_measurement": "unknown",
                },
            ),
            30,
            "moisture",
        ),
        # Test conductivity
        (
            Mock(
                state="500",
                attributes={
                    "device_class": "conductivity",
                    "unit_of_measurement": UnitOfConductivity.MICROSIEMENS_PER_CM,
                },
            ),
            500,
            None,
        ),
        # Test conductivity out of range
        (
            Mock(
                state="5000",
                attributes={
                    "device_class": "conductivity",
                    "unit_of_measurement": UnitOfConductivity.MICROSIEMENS_PER_CM,
                },
            ),
            5000,
            "conductivity",
        ),
        # Test unsupported conductivity unit
        (
            Mock(
                state="500",
                attributes={
                    "device_class": "conductivity",
                    "unit_of_measurement": "unknown",
                },
            ),
            500,
            "conductivity",
        ),
        # Test unsupported device_class
        (
            Mock(
                state="50",
                attributes={
                    "device_class": "unsupported",
                    "unit_of_measurement": PERCENTAGE,
                },
            ),
            50,
            "device_class",
        ),
        # Test invalid state
        (
            Mock(
                state="invalid_state",
                attributes={
                    "device_class": "moisture",
                    "unit_of_measurement": PERCENTAGE,
                },
            ),
            None,
            "moisture",
        ),
    ],
)
def test_get_supported_state_value(state, expected_value, expected_error):
    value, error = get_supported_state_value(state)
    assert value == expected_value
    assert error == expected_error
