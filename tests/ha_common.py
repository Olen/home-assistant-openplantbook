"""Test helpers from whichever Home Assistant test package is installed.

HA 2026.11 replaced pytest-homeassistant-custom-component with the official
pytest-home-assistant. CI runs both until 2026.11 is the lowest tested HA.
"""

try:
    from pytest_homeassistant.common import MockConfigEntry

    OFFICIAL_TEST_PACKAGE = True
except ImportError:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    OFFICIAL_TEST_PACKAGE = False

__all__ = ["OFFICIAL_TEST_PACKAGE", "MockConfigEntry"]
