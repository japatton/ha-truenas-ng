"""Tests for the truenas_ng switch platform."""
from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.truenas_ng.const import DOMAIN

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


async def test_service_switches_created(hass: HomeAssistant, init_integration) -> None:
    """One CONFIG-category switch per service (3 in the fixture)."""
    registry = er.async_get(hass)
    switches = [
        e
        for e in registry.entities.values()
        if e.domain == "switch" and e.platform == DOMAIN
    ]
    assert len(switches) == 3
    unique_ids = {e.unique_id for e in switches}
    assert f"{HOST_ID}_service_ssh_switch" in unique_ids
    assert f"{HOST_ID}_service_cifs_switch" in unique_ids
    assert f"{HOST_ID}_service_nfs_switch" in unique_ids
    for e in switches:
        assert e.entity_category is EntityCategory.CONFIG


async def test_switch_state_reflects_running(hass: HomeAssistant, init_integration) -> None:
    """ssh is RUNNING -> on; nfs is STOPPED -> off."""
    registry = er.async_get(hass)
    ssh = registry.async_get_entity_id("switch", DOMAIN, f"{HOST_ID}_service_ssh_switch")
    nfs = registry.async_get_entity_id("switch", DOMAIN, f"{HOST_ID}_service_nfs_switch")
    assert hass.states.get(ssh).state == "on"
    assert hass.states.get(nfs).state == "off"


async def test_switch_turn_on_calls_service_control(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """Turning a switch on calls service.control START with job=True."""
    registry = er.async_get(hass)
    nfs = registry.async_get_entity_id("switch", DOMAIN, f"{HOST_ID}_service_nfs_switch")

    mock_client.call.reset_mock()
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": nfs}, blocking=True
    )
    await hass.async_block_till_done()

    control = [c for c in mock_client.call.call_args_list if c.args[0] == "service.control"]
    assert control[0].args == ("service.control", "START", "nfs")
    assert control[0].kwargs == {"job": True}


async def test_switch_turn_off_calls_service_control(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """Turning a switch off calls service.control STOP with job=True."""
    registry = er.async_get(hass)
    ssh = registry.async_get_entity_id("switch", DOMAIN, f"{HOST_ID}_service_ssh_switch")

    mock_client.call.reset_mock()
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": ssh}, blocking=True
    )
    await hass.async_block_till_done()

    control = [c for c in mock_client.call.call_args_list if c.args[0] == "service.control"]
    assert control[0].args == ("service.control", "STOP", "ssh")
    assert control[0].kwargs == {"job": True}


async def test_switches_absent_when_disabled(hass: HomeAssistant, mock_client) -> None:
    """With service controls disabled via options, no switches are created."""
    from unittest.mock import patch

    from homeassistant.const import (
        CONF_API_KEY,
        CONF_HOST,
        CONF_PORT,
        CONF_USERNAME,
        CONF_VERIFY_SSL,
    )
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.truenas_ng.const import CONF_ENABLE_SERVICE_CONTROLS

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
        options={CONF_ENABLE_SERVICE_CONTROLS: False},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.truenas_ng.TrueNASClient", return_value=mock_client
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    switches = [
        e
        for e in registry.entities.values()
        if e.domain == "switch" and e.platform == DOMAIN
    ]
    assert switches == []
