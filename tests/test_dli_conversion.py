"""Tests for DLI conversion from OpenPlantbook mmol values."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook import _enrich_plant_data_with_dli
from custom_components.openplantbook.const import (
    ATTR_SPECIES,
    DOMAIN,
    OPB_SERVICE_GET,
)


class TestEnrichPlantDataWithDli:
    """Unit tests for _enrich_plant_data_with_dli."""

    def test_normal_ratio_uses_0036_factor(self):
        """Test that normal mmol/lux ratio uses × 0.0036 conversion."""
        # Capsicum annuum: full sun plant
        data = {
            "display_pid": "Capsicum annuum",
            "max_light_mmol": 12000,
            "min_light_mmol": 3500,
            "max_light_lux": 95000,
            "min_light_lux": 6000,
        }
        _enrich_plant_data_with_dli(data)

        assert data["max_dli"] == 43.2  # 12000 × 0.0036
        assert data["min_dli"] == 12.6  # 3500 × 0.0036

    def test_high_ratio_uses_divide_1000(self):
        """Test that high mmol/lux ratio switches to / 1000 conversion."""
        # Simulated data where mmol values are daily integrals
        data = {
            "display_pid": "Test plant",
            "max_light_mmol": 6000,
            "min_light_mmol": 2000,
            "max_light_lux": 2500,  # ratio = 6000/2500 = 2.4 (> 0.5)
            "min_light_lux": 500,
        }
        _enrich_plant_data_with_dli(data)

        assert data["max_dli"] == 6.0  # 6000 / 1000
        assert data["min_dli"] == 2.0  # 2000 / 1000

    def test_low_ratio_warns_and_uses_default(self, caplog):
        """Test that unusually low ratio logs warning but uses × 0.0036."""
        data = {
            "display_pid": "Weird plant",
            "max_light_mmol": 100,
            "min_light_mmol": 10,
            "max_light_lux": 50000,  # ratio = 100/50000 = 0.002 (< 0.02)
            "min_light_lux": 5000,
        }
        with caplog.at_level(logging.WARNING):
            _enrich_plant_data_with_dli(data)

        assert data["max_dli"] == 0.4  # 100 × 0.0036 = 0.36, rounded to 0.4
        assert "Unusual mmol/lux ratio" in caplog.text

    def test_no_mmol_values(self):
        """Test that missing mmol values result in no DLI attributes."""
        data = {
            "display_pid": "No mmol plant",
            "max_light_lux": 20000,
            "min_light_lux": 1000,
        }
        _enrich_plant_data_with_dli(data)

        assert "max_dli" not in data
        assert "min_dli" not in data

    def test_no_lux_values_uses_default_factor(self):
        """Test that missing lux values still compute DLI with default factor."""
        data = {
            "display_pid": "No lux plant",
            "max_light_mmol": 5000,
            "min_light_mmol": 800,
        }
        _enrich_plant_data_with_dli(data)

        assert data["max_dli"] == 18.0  # 5000 × 0.0036
        assert data["min_dli"] == 2.9  # 800 × 0.0036 = 2.88

    def test_zero_lux_uses_default_factor(self):
        """Test that zero lux avoids division by zero and uses default factor."""
        data = {
            "display_pid": "Zero lux plant",
            "max_light_mmol": 5000,
            "min_light_mmol": 800,
            "max_light_lux": 0,
        }
        _enrich_plant_data_with_dli(data)

        assert data["max_dli"] == 18.0
        assert data["min_dli"] == 2.9

    def test_only_max_mmol(self):
        """Test with only max_light_mmol present."""
        data = {
            "display_pid": "Partial data",
            "max_light_mmol": 8000,
            "max_light_lux": 40000,
        }
        _enrich_plant_data_with_dli(data)

        assert data["max_dli"] == 28.8
        assert "min_dli" not in data

    def test_only_min_mmol(self):
        """Test with only min_light_mmol present."""
        data = {
            "display_pid": "Partial data",
            "min_light_mmol": 1500,
            "max_light_lux": 20000,
        }
        _enrich_plant_data_with_dli(data)

        assert "max_dli" not in data
        assert data["min_dli"] == 5.4

    def test_borderline_ratio_at_max_threshold(self):
        """Test ratio exactly at 0.5 uses × 0.0036."""
        data = {
            "display_pid": "Borderline plant",
            "max_light_mmol": 5000,
            "min_light_mmol": 1000,
            "max_light_lux": 10000,  # ratio = 0.5 exactly
        }
        _enrich_plant_data_with_dli(data)

        assert data["max_dli"] == 18.0  # × 0.0036
        assert data["min_dli"] == 3.6

    def test_ratio_just_above_max_uses_divide_1000(self):
        """Test ratio just above 0.5 switches to / 1000."""
        data = {
            "display_pid": "Just above plant",
            "max_light_mmol": 5100,
            "min_light_mmol": 1000,
            "max_light_lux": 10000,  # ratio = 0.51
        }
        _enrich_plant_data_with_dli(data)

        assert data["max_dli"] == 5.1  # / 1000
        assert data["min_dli"] == 1.0

    def test_high_ratio_logs_info(self, caplog):
        """Test that high ratio conversion logs an info message."""
        data = {
            "display_pid": "Daily integral plant",
            "max_light_mmol": 30000,
            "min_light_mmol": 5000,
            "max_light_lux": 10000,  # ratio = 3.0
        }
        with caplog.at_level(logging.INFO):
            _enrich_plant_data_with_dli(data)

        assert "daily integrals" in caplog.text
        assert data["max_dli"] == 30.0
        assert data["min_dli"] == 5.0

    def test_known_plants_produce_reasonable_dli(self):
        """Test that known plants from OPB produce reasonable DLI values."""
        # Data from actual OPB API responses
        plants = [
            # (name, max_mmol, max_lux, expected_dli_range)
            ("Capsicum annuum", 12000, 95000, (30, 60)),  # full sun
            ("Monstera deliciosa", 5000, 30000, (10, 25)),  # medium-high
            ("Ficus elastica", 4000, 25000, (10, 20)),  # medium
        ]
        for name, max_mmol, max_lux, (dli_min, dli_max) in plants:
            data = {
                "display_pid": name,
                "max_light_mmol": max_mmol,
                "max_light_lux": max_lux,
            }
            _enrich_plant_data_with_dli(data)
            assert (
                dli_min <= data["max_dli"] <= dli_max
            ), f"{name}: max_dli={data['max_dli']} not in range {dli_min}-{dli_max}"


class TestDliConversionIntegration:
    """Integration tests: verify DLI is added via the get service."""

    async def test_get_plant_includes_dli_attributes(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test that get plant service returns DLI attributes when mmol data present."""
        # Update mock to include mmol values
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            return_value={
                "pid": "capsicum annuum",
                "display_pid": "Capsicum annuum",
                "max_light_lux": 95000,
                "min_light_lux": 6000,
                "max_light_mmol": 12000,
                "min_light_mmol": 3500,
                "max_temp": 35,
                "min_temp": 10,
            }
        )

        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "capsicum annuum"},
            blocking=True,
            return_response=True,
        )

        assert result["max_dli"] == 43.2
        assert result["min_dli"] == 12.6

        # Also verify entity state has the DLI attributes
        state = hass.states.get("openplantbook.capsicum_annuum")
        assert state is not None
        assert state.attributes["max_dli"] == 43.2
        assert state.attributes["min_dli"] == 12.6

    async def test_get_plant_without_mmol_has_no_dli(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test that plants without mmol data don't get DLI attributes."""
        # Default mock doesn't include mmol values
        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "monstera deliciosa"},
            blocking=True,
            return_response=True,
        )

        assert "max_dli" not in result
        assert "min_dli" not in result

    async def test_get_plant_dli_with_high_ratio(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_openplantbook_api: MagicMock,
    ) -> None:
        """Test that high mmol/lux ratio plant uses / 1000 conversion."""
        mock_openplantbook_api.async_plant_detail_get = AsyncMock(
            return_value={
                "pid": "shade plant",
                "display_pid": "Shade plant",
                "max_light_lux": 2500,
                "min_light_lux": 500,
                "max_light_mmol": 6000,  # ratio = 2.4
                "min_light_mmol": 2000,
            }
        )

        result = await hass.services.async_call(
            DOMAIN,
            OPB_SERVICE_GET,
            {"species": "shade plant"},
            blocking=True,
            return_response=True,
        )

        assert result["max_dli"] == 6.0  # / 1000
        assert result["min_dli"] == 2.0
