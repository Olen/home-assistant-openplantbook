"""Tests for the uploader module."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfConductivity,
    UnitOfTemperature,
)

from custom_components.openplantbook.uploader import get_supported_state_value


class TestGetSupportedStateValue:
    """Tests for get_supported_state_value function."""

    @pytest.mark.parametrize(
        "state, expected_value, expected_error",
        [
            # Test temperature in Fahrenheit - converts to Celsius
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
            # Test temperature in Kelvin - converts to Celsius
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
            # Test temperature in Celsius - valid range
            (
                Mock(
                    state="25",
                    attributes={
                        "device_class": "temperature",
                        "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    },
                ),
                25,
                None,
            ),
            # Test temperature out of range (too high)
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
            # Test temperature out of range (too low)
            (
                Mock(
                    state="-60",
                    attributes={
                        "device_class": "temperature",
                        "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    },
                ),
                -60,
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
        ],
    )
    def test_temperature_conversion(self, state, expected_value, expected_error):
        """Test temperature value handling and conversions."""
        value, error = get_supported_state_value(state)
        assert value == expected_value
        assert error == expected_error

    @pytest.mark.parametrize(
        "state, expected_value, expected_error",
        [
            # Test humidity valid
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
            # Test humidity at boundary (0%)
            (
                Mock(
                    state="0",
                    attributes={
                        "device_class": "humidity",
                        "unit_of_measurement": PERCENTAGE,
                    },
                ),
                0,
                None,
            ),
            # Test humidity at boundary (100%)
            (
                Mock(
                    state="100",
                    attributes={
                        "device_class": "humidity",
                        "unit_of_measurement": PERCENTAGE,
                    },
                ),
                100,
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
        ],
    )
    def test_humidity_handling(self, state, expected_value, expected_error):
        """Test humidity value handling."""
        value, error = get_supported_state_value(state)
        assert value == expected_value
        assert error == expected_error

    @pytest.mark.parametrize(
        "state, expected_value, expected_error",
        [
            # Test illuminance valid
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
            # Test illuminance at boundary (0 lx)
            (
                Mock(
                    state="0",
                    attributes={
                        "device_class": "illuminance",
                        "unit_of_measurement": LIGHT_LUX,
                    },
                ),
                0,
                None,
            ),
            # Test illuminance at boundary (200000 lx)
            (
                Mock(
                    state="200000",
                    attributes={
                        "device_class": "illuminance",
                        "unit_of_measurement": LIGHT_LUX,
                    },
                ),
                200000,
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
        ],
    )
    def test_illuminance_handling(self, state, expected_value, expected_error):
        """Test illuminance value handling."""
        value, error = get_supported_state_value(state)
        assert value == expected_value
        assert error == expected_error

    @pytest.mark.parametrize(
        "state, expected_value, expected_error",
        [
            # Test moisture valid
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
        ],
    )
    def test_moisture_handling(self, state, expected_value, expected_error):
        """Test moisture value handling."""
        value, error = get_supported_state_value(state)
        assert value == expected_value
        assert error == expected_error

    @pytest.mark.parametrize(
        "state, expected_value, expected_error",
        [
            # Test conductivity valid
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
            # Test conductivity at boundary (0)
            (
                Mock(
                    state="0",
                    attributes={
                        "device_class": "conductivity",
                        "unit_of_measurement": UnitOfConductivity.MICROSIEMENS_PER_CM,
                    },
                ),
                0,
                None,
            ),
            # Test conductivity at boundary (3000)
            (
                Mock(
                    state="3000",
                    attributes={
                        "device_class": "conductivity",
                        "unit_of_measurement": UnitOfConductivity.MICROSIEMENS_PER_CM,
                    },
                ),
                3000,
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
        ],
    )
    def test_conductivity_handling(self, state, expected_value, expected_error):
        """Test conductivity value handling."""
        value, error = get_supported_state_value(state)
        assert value == expected_value
        assert error == expected_error

    def test_unsupported_device_class(self):
        """Test handling of unsupported device class."""
        state = Mock(
            state="50",
            attributes={
                "device_class": "unsupported",
                "unit_of_measurement": PERCENTAGE,
            },
        )
        value, error = get_supported_state_value(state)
        assert value == 50
        assert error == "device_class"

    def test_invalid_state_non_numeric(self):
        """Test handling of non-numeric state values."""
        state = Mock(
            state="invalid_state",
            attributes={
                "device_class": "moisture",
                "unit_of_measurement": PERCENTAGE,
            },
        )
        value, error = get_supported_state_value(state)
        assert value is None
        assert error == "moisture"

    def test_float_state_rounded(self):
        """Test that float state values are rounded to integers."""
        state = Mock(
            state="25.7",
            attributes={
                "device_class": "temperature",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
        )
        value, error = get_supported_state_value(state)
        assert value == 26
        assert error is None
