"""Tests for the truenas_ng binary_sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from custom_components.truenas_ng.const import DOMAIN

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
DATA_POOL_GUID = "1111111111111111111"
SDA_SERIAL = "WD-DEADBEEF01"


async def _setup_binary_sensor_only(
    hass: HomeAssistant, mock_client: MagicMock
) -> MockConfigEntry:
    """Set up the integration with PLATFORMS patched to [Platform.BINARY_SENSOR] only."""
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
    with (
        patch("custom_components.truenas_ng.TrueNASClient", return_value=mock_client),
        patch("custom_components.truenas_ng.PLATFORMS", [Platform.BINARY_SENSOR]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_pool_health_binary_sensor_off_when_healthy(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Data pool is ONLINE and healthy -> PROBLEM sensor is off."""
    await _setup_binary_sensor_only(hass, mock_client)
    registry = er.async_get(hass)
    unique_id = f"{HOST_ID}_pool_{DATA_POOL_GUID}_health"
    entity_id = registry.async_get_entity_id("binary_sensor", "truenas_ng", unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"
    assert state.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM


async def test_disk_problem_binary_sensor_off_for_clean_disk(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """sda is ONLINE with zero ZFS error counters -> PROBLEM sensor is off."""
    await _setup_binary_sensor_only(hass, mock_client)
    registry = er.async_get(hass)
    unique_id = f"{HOST_ID}_disk_{SDA_SERIAL}_problem"
    entity_id = registry.async_get_entity_id("binary_sensor", "truenas_ng", unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"
    assert state.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM


async def test_service_running_binary_sensors(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """cifs is RUNNING -> on; nfs is STOPPED -> off; device_class RUNNING."""
    await _setup_binary_sensor_only(hass, mock_client)
    registry = er.async_get(hass)

    cifs_entity = registry.async_get_entity_id(
        "binary_sensor", "truenas_ng", f"{HOST_ID}_service_cifs_running"
    )
    nfs_entity = registry.async_get_entity_id(
        "binary_sensor", "truenas_ng", f"{HOST_ID}_service_nfs_running"
    )
    assert cifs_entity is not None
    assert nfs_entity is not None

    cifs_state = hass.states.get(cifs_entity)
    nfs_state = hass.states.get(nfs_entity)
    assert cifs_state is not None
    assert nfs_state is not None
    assert cifs_state.state == "on"
    assert nfs_state.state == "off"
    assert cifs_state.attributes["device_class"] == BinarySensorDeviceClass.RUNNING


async def test_critical_alert_binary_sensor_on(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """A non-dismissed CRITICAL alert (SMARTFailed) -> PROBLEM sensor is on."""
    await _setup_binary_sensor_only(hass, mock_client)
    registry = er.async_get(hass)
    unique_id = f"{HOST_ID}_alerts_critical"
    entity_id = registry.async_get_entity_id("binary_sensor", "truenas_ng", unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM
