"""Trigger platform for openplantbook (Home Assistant 2026.7+).

Exposes openplantbook.upload_* triggers for the health of the plant-sensor
upload. Import-safe on every supported HA version: the 2026.7-only helper API
is imported lazily, so on older HA async_get_triggers returns {}.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_TRIGGERS_CACHE: dict[str, type] | None = None


def _has_purpose_trigger_api() -> bool:
    """True when the HA 2026.7 purpose-trigger API is importable.

    The earlier Labs form (2026.2-2026.6) had a different API, so this checks
    symbols that only exist from 2026.7.
    """
    try:
        from homeassistant.helpers.automation import DomainSpec  # noqa: F401
        from homeassistant.helpers.trigger import (  # noqa: F401
            make_entity_target_state_trigger,
        )
    except ImportError:
        return False
    return True


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type]:
    """Return the openplantbook.* triggers, or {} on HA without the 2026.7 API."""
    global _TRIGGERS_CACHE
    if not _has_purpose_trigger_api():
        return {}
    if _TRIGGERS_CACHE is None:
        from .trigger_impl import build_triggers

        _TRIGGERS_CACHE = build_triggers()
    return _TRIGGERS_CACHE
