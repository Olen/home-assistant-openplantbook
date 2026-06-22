"""Verify every config/options flow form field is translated.

Mirrors Home Assistant core's flow-translation pylint checks
(config-flow-field-not-translated / options-flow-field-not-translated): every
voluptuous field in a flow step must have a ``<flow>.step.<step>.data.<field>``
entry. We additionally require the same entry in ``translations/en.json`` (what
HA actually reads at runtime), not just ``strings.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.openplantbook.const import DOMAIN

COMPONENT = (
    Path(__file__).resolve().parent.parent / "custom_components" / "openplantbook"
)


def _load(name: str) -> dict:
    return json.loads((COMPONENT / name).read_text(encoding="utf-8"))


def _field_names(data_schema) -> set[str]:
    """Return the field keys of a voluptuous schema (markers or plain keys)."""
    return {str(getattr(marker, "schema", marker)) for marker in data_schema.schema}


def _translated_keys(translations: dict, flow: str, step: str) -> set[str]:
    node = translations.get(flow, {}).get("step", {}).get(step, {})
    keys = set(node.get("data", {}).keys())
    for section in node.get("sections", {}).values():
        keys |= set(section.get("data", {}).keys())
    return keys


def _assert_step_translated(flow: str, step: str, data_schema) -> None:
    fields = _field_names(data_schema)
    for filename, data in (
        ("strings.json", _load("strings.json")),
        ("translations/en.json", _load("translations/en.json")),
    ):
        missing = fields - _translated_keys(data, flow, step)
        assert not missing, (
            f"{filename}: {flow}.step.{step} is missing data labels for "
            f"{sorted(missing)}"
        )


async def test_config_flow_fields_translated(hass: HomeAssistant) -> None:
    """Every config flow step's form fields are translated."""
    with patch(
        "custom_components.openplantbook.config_flow.OpenPlantBookApi"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api._async_get_token = AsyncMock(return_value="test_token")
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        _assert_step_translated("config", "user", result["data_schema"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CLIENT_ID: "valid_id", CONF_CLIENT_SECRET: "valid_secret"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "upload"
        _assert_step_translated("config", "upload", result["data_schema"])


async def test_options_flow_fields_translated(
    hass: HomeAssistant,
    mock_openplantbook_api: MagicMock,
    init_integration,
) -> None:
    """Every options flow step's form fields are translated."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    _assert_step_translated("options", "init", result["data_schema"])
