"""Tests for the truenas_ng update platform."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.truenas_ng.const import DOMAIN

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

_AVAILABLE_STATUS = {
    "code": "NORMAL",
    "status": {
        "current_version": {
            "train": "TrueNAS-26-BETA",
            "profile": "EARLY_ADOPTER",
            "matches_profile": True,
        },
        "new_version": {"version": "26.0.1"},
    },
    "error": None,
    "update_download_progress": None,
}


async def _setup(hass: HomeAssistant, mock_client) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST_ID,
        data={
            CONF_HOST: "truenas.local",
            CONF_PORT: 9443,
            CONF_USERNAME: "homeassistant",
            CONF_API_KEY: "1-test",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.truenas_ng.TrueNASClient", return_value=mock_client
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_update_entity_up_to_date(hass: HomeAssistant, init_integration) -> None:
    """With new_version null, the update entity exists and reports 'off'."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("update", DOMAIN, f"{HOST_ID}_os_update")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state.state == "off"
    assert state.attributes["installed_version"] == "26.0.0-BETA.1"
    assert state.attributes["latest_version"] == "26.0.0-BETA.1"


async def test_update_entity_available(hass: HomeAssistant, mock_client) -> None:
    """With new_version set, the update entity reports 'on' and the latest version."""
    mock_client._dispatch["update.status"] = _AVAILABLE_STATUS
    await _setup(hass, mock_client)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("update", DOMAIN, f"{HOST_ID}_os_update")
    state = hass.states.get(entity_id)
    assert state.state == "on"
    assert state.attributes["latest_version"] == "26.0.1"


async def test_update_install_calls_update_run(
    hass: HomeAssistant, mock_client
) -> None:
    """Installing the update calls update.run with job=True."""
    mock_client._dispatch["update.status"] = _AVAILABLE_STATUS
    await _setup(hass, mock_client)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("update", DOMAIN, f"{HOST_ID}_os_update")

    mock_client.call.reset_mock()
    await hass.services.async_call(
        "update", "install", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    run = [c for c in mock_client.call.call_args_list if c.args[0] == "update.run"]
    assert run and run[0].kwargs == {"job": True}
