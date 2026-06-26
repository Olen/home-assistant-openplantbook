"""Tests for DLI conversion from OpenPlantbook mmol values."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook import _clamp_dli, _enrich_plant_data_with_dli
from custom_components.openplantbook.const import (
    DLI_SANITY_MAX,
    DOMAIN,
    OPB_DISPLAY_PID,
    OPB_MAX_DLI,
    OPB_MAX_LIGHT_LUX,
    OPB_MAX_LIGHT_MMOL,
    OPB_MIN_DLI,
    OPB_MIN_LIGHT_MMOL,
    OPB_SERVICE_GET,
)


class TestEnrichPlantDataWithDli:
    """Unit tests for _enrich_plant_data_with_dli."""

    def test_full_sun_plant_uses_divide_1000(self):
        """Test that mmol values are converted to DLI via / 1000."""
        # Capsicum annuum: full sun plant
        data = {
            OPB_DISPLAY_PID: "Capsicum annuum",
            OPB_MAX_LIGHT_MMOL: 12000,
            OPB_MIN_LIGHT_MMOL: 3500,
            OPB_MAX_LIGHT_LUX: 95000,
            "min_light_lux": 6000,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 12.0  # 12000 / 1000
        assert data[OPB_MIN_DLI] == 3.5  # 3500 / 1000

    def test_moderate_light_plant(self):
        """Test conversion for moderate light plant."""
        data = {
            OPB_DISPLAY_PID: "Test plant",
            OPB_MAX_LIGHT_MMOL: 6000,
            OPB_MIN_LIGHT_MMOL: 2000,
            OPB_MAX_LIGHT_LUX: 2500,
            "min_light_lux": 500,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 6.0  # 6000 / 1000
        assert data[OPB_MIN_DLI] == 2.0  # 2000 / 1000

    def test_low_light_plant(self):
        """Test conversion for low light plant."""
        data = {
            OPB_DISPLAY_PID: "Shade plant",
            OPB_MAX_LIGHT_MMOL: 100,
            OPB_MIN_LIGHT_MMOL: 10,
            OPB_MAX_LIGHT_LUX: 50000,
            "min_light_lux": 5000,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 0.1  # 100 / 1000
        assert data[OPB_MIN_DLI] == 0.0  # 10 / 1000 = 0.01, rounded to 0.0

    def test_no_mmol_values(self):
        """Test that missing mmol values result in no DLI attributes."""
        data = {
            OPB_DISPLAY_PID: "No mmol plant",
            OPB_MAX_LIGHT_LUX: 20000,
            "min_light_lux": 1000,
        }
        _enrich_plant_data_with_dli(data)

        assert OPB_MAX_DLI not in data
        assert OPB_MIN_DLI not in data

    def test_no_lux_values_still_computes_dli(self):
        """Test that missing lux values still compute DLI."""
        data = {
            OPB_DISPLAY_PID: "No lux plant",
            OPB_MAX_LIGHT_MMOL: 5000,
            OPB_MIN_LIGHT_MMOL: 800,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 5.0  # 5000 / 1000
        assert data[OPB_MIN_DLI] == 0.8  # 800 / 1000

    def test_zero_lux_still_computes_dli(self):
        """Test that zero lux still computes DLI (lux not used)."""
        data = {
            OPB_DISPLAY_PID: "Zero lux plant",
            OPB_MAX_LIGHT_MMOL: 5000,
            OPB_MIN_LIGHT_MMOL: 800,
            OPB_MAX_LIGHT_LUX: 0,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 5.0
        assert data[OPB_MIN_DLI] == 0.8

    def test_only_max_mmol(self):
        """Test with only max_light_mmol present."""
        data = {
            OPB_DISPLAY_PID: "Partial data",
            OPB_MAX_LIGHT_MMOL: 8000,
            OPB_MAX_LIGHT_LUX: 40000,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 8.0  # 8000 / 1000
        assert OPB_MIN_DLI not in data

    def test_only_min_mmol(self):
        """Test with only min_light_mmol present."""
        data = {
            OPB_DISPLAY_PID: "Partial data",
            OPB_MIN_LIGHT_MMOL: 1500,
            OPB_MAX_LIGHT_LUX: 20000,
        }
        _enrich_plant_data_with_dli(data)

        assert OPB_MAX_DLI not in data
        assert data[OPB_MIN_DLI] == 1.5  # 1500 / 1000

    def test_high_light_plant(self):
        """Test conversion for high light plant."""
        data = {
            OPB_DISPLAY_PID: "High light plant",
            OPB_MAX_LIGHT_MMOL: 5000,
            OPB_MIN_LIGHT_MMOL: 1000,
            OPB_MAX_LIGHT_LUX: 10000,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 5.0  # 5000 / 1000
        assert data[OPB_MIN_DLI] == 1.0  # 1000 / 1000

    def test_very_high_mmol(self):
        """Test conversion for very high mmol values."""
        data = {
            OPB_DISPLAY_PID: "Very high plant",
            OPB_MAX_LIGHT_MMOL: 5100,
            OPB_MIN_LIGHT_MMOL: 1000,
            OPB_MAX_LIGHT_LUX: 10000,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 5.1  # 5100 / 1000
        assert data[OPB_MIN_DLI] == 1.0

    def test_extreme_mmol_values(self):
        """Test conversion for extreme mmol values."""
        data = {
            OPB_DISPLAY_PID: "Extreme light plant",
            OPB_MAX_LIGHT_MMOL: 30000,
            OPB_MIN_LIGHT_MMOL: 5000,
            OPB_MAX_LIGHT_LUX: 10000,
        }
        _enrich_plant_data_with_dli(data)

        assert data[OPB_MAX_DLI] == 30.0  # 30000 / 1000
        assert data[OPB_MIN_DLI] == 5.0  # 5000 / 1000

    def test_known_plants_produce_reasonable_dli(self):
        """Test that known plants from OPB produce reasonable DLI values.

        DLI reference ranges from House Plant Journal PAR-meter data:
        - Capsicum (full sun): 8-20 mol/m²/d
        - Monstera (moderate): 2-5 mol/m²/d
        - Ficus elastica (moderate): 4-12 mol/m²/d
        """
        # Data from actual OPB API responses, converted via the mmol→mol factor.
        # Expected ranges match the House Plant Journal references above.
        plants = [
            # (name, max_mmol, max_lux, expected_dli_range)
            ("Capsicum annuum", 12000, 95000, (8, 20)),  # full sun: 12.0 DLI
            ("Monstera deliciosa", 5000, 30000, (2, 5)),  # moderate: 5.0 DLI
            ("Ficus elastica", 4000, 25000, (4, 12)),  # moderate: 4.0 DLI
        ]
        for name, max_mmol, max_lux, (dli_min, dli_max) in plants:
            data = {
                OPB_DISPLAY_PID: name,
                OPB_MAX_LIGHT_MMOL: max_mmol,
                OPB_MAX_LIGHT_LUX: max_lux,
            }
            _enrich_plant_data_with_dli(data)
            assert (
                dli_min <= data[OPB_MAX_DLI] <= dli_max
            ), f"{name}: max_dli={data[OPB_MAX_DLI]} not in range {dli_min}-{dli_max}"


class TestDliSanityClamp:
    """Tests for the DLI sanity clamp on converted values."""

    def test_value_in_band_unchanged(self):
        """A plausible DLI passes through untouched."""
        assert _clamp_dli(12.0, "max", "Capsicum annuum") == 12.0
        assert _clamp_dli(0.7, "min", "Pellaea rotundifolia") == 0.7

    def test_near_zero_minimum_not_clamped(self):
        """Legitimate deep-shade minimums (rounding toward 0) are preserved."""
        assert _clamp_dli(0.0, "min", "Pellaea rotundifolia") == 0.0

    def test_clamps_impossible_high_value(self, caplog):
        """A value above Earth's physical max DLI is clamped + warned."""
        result = _clamp_dli(120.0, "max", "Corrupt entry")
        assert result == DLI_SANITY_MAX
        assert "exceeds the plausible maximum" in caplog.text

    def test_enrich_clamps_absurd_mmol(self, caplog):
        """End-to-end: an absurd max_light_mmol yields a clamped DLI."""
        # 100000000 mmol would be 100000 mol/m²/d — clearly corrupt source data.
        data = {
            OPB_DISPLAY_PID: "Corrupt entry",
            OPB_MAX_LIGHT_MMOL: 100000000,
            OPB_MIN_LIGHT_MMOL: 2000,
        }
        _enrich_plant_data_with_dli(data)
        assert data[OPB_MAX_DLI] == DLI_SANITY_MAX
        assert data[OPB_MIN_DLI] == 2.0  # normal value untouched
        assert "exceeds the plausible maximum" in caplog.text


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

        assert result[OPB_MAX_DLI] == 12.0  # 12000 / 1000
        assert result[OPB_MIN_DLI] == 3.5  # 3500 / 1000

        # Also verify entity state has the DLI attributes
        state = hass.states.get("openplantbook.capsicum_annuum")
        assert state is not None
        assert state.attributes[OPB_MAX_DLI] == 12.0
        assert state.attributes[OPB_MIN_DLI] == 3.5

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

        assert OPB_MAX_DLI not in result
        assert OPB_MIN_DLI not in result

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

        assert result[OPB_MAX_DLI] == 6.0  # / 1000
        assert result[OPB_MIN_DLI] == 2.0
