"""Tests for the truenas_ng sensor platform."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
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
DATA_GUID = "1111111111111111111"
SDA_SERIAL = "WD-DEADBEEF01"


async def _setup_sensor_only(
    hass: HomeAssistant,
    mock_client: MagicMock,
    options: dict | None = None,
) -> MockConfigEntry:
    """Set up the integration with PLATFORMS patched to [Platform.SENSOR] only."""
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
        options=options or {},
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.truenas_ng.TrueNASClient", return_value=mock_client),
        patch("custom_components.truenas_ng.PLATFORMS", [Platform.SENSOR]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, entity_registry: er.EntityRegistry, unique_id: str):
    """Resolve an entity_id from its unique_id, then return its state object."""
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None, f"no sensor registered for unique_id {unique_id}"
    return hass.states.get(entity_id)


async def test_pool_sensors(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Pool status + derived used_pct expose the values from pool_query.json."""
    await _setup_sensor_only(hass, mock_client)
    entity_registry = er.async_get(hass)

    status = _state(hass, entity_registry, f"{HOST_ID}_pool_{DATA_GUID}_status")
    assert status is not None
    assert status.state == "ONLINE"

    used_pct = _state(hass, entity_registry, f"{HOST_ID}_pool_{DATA_GUID}_used_pct")
    assert used_pct is not None
    # allocated 15774153986048 / size 19997367730176 * 100 -> round(…, 1)
    assert used_pct.state == "78.9"
    assert used_pct.attributes["unit_of_measurement"] == "%"


async def test_disk_temperature_sensor(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The sda disk temperature sensor reports 37.0 °C from disk_temperatures.json."""
    await _setup_sensor_only(hass, mock_client)
    entity_registry = er.async_get(hass)

    temp = _state(hass, entity_registry, f"{HOST_ID}_disk_{SDA_SERIAL}_temp")
    assert temp is not None
    assert temp.state == "37.0"
    assert temp.attributes["unit_of_measurement"] == "°C"
    assert temp.attributes["device_class"] == "temperature"


async def test_reporting_sensors(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """CPU usage and derived memory-used-% come from reporting_get_data.json + physmem."""
    await _setup_sensor_only(hass, mock_client)
    entity_registry = er.async_get(hass)

    cpu = _state(hass, entity_registry, f"{HOST_ID}_system_cpu_percent")
    assert cpu is not None
    assert cpu.state == "2"
    assert cpu.attributes["state_class"] == "measurement"

    mem_pct = _state(hass, entity_registry, f"{HOST_ID}_system_memory_used_pct")
    assert mem_pct is not None
    # physmem 65123586048, available 30234440000 -> used 34889146048 -> 53.6 %
    assert mem_pct.state == "53.6"
    assert mem_pct.attributes["unit_of_measurement"] == "%"


async def test_dataset_sensor_disabled_by_default(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Dataset sensors are registered but disabled by default (no live state)."""
    from custom_components.truenas_ng.const import CONF_ENABLE_DATASETS

    await _setup_sensor_only(hass, mock_client, options={CONF_ENABLE_DATASETS: True})
    entity_registry = er.async_get(hass)

    unique_id = f"{HOST_ID}_dataset_Data_used"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None, "dataset used sensor should be registered"

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is not None
    assert entry.disabled is True
    # disabled entities are not added to the state machine
    assert hass.states.get(entity_id) is None


async def test_alerts_sensor_counts_active(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """The active-alerts sensor counts non-dismissed alert.list entries (2)."""
    await _setup_sensor_only(hass, mock_client)
    entity_registry = er.async_get(hass)

    alerts = _state(hass, entity_registry, f"{HOST_ID}_alerts_active")
    assert alerts is not None
    assert alerts.state == "2"
    assert alerts.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


async def test_datasets_absent_by_default(hass, mock_client) -> None:
    """With no options set, datasets default off -> no dataset sensors created."""
    from unittest.mock import patch

    from homeassistant.const import (
        CONF_API_KEY,
        CONF_HOST,
        CONF_PORT,
        CONF_USERNAME,
        CONF_VERIFY_SSL,
    )
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.truenas_ng.const import DOMAIN

    host_id = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=host_id,
        data={
            CONF_HOST: "truenas.local",
            CONF_PORT: 9443,
            CONF_USERNAME: "homeassistant",
            CONF_API_KEY: "1-test",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)
    with patch("custom_components.truenas_ng.TrueNASClient", return_value=mock_client):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    dataset_entities = [
        e
        for e in registry.entities.values()
        if e.platform == DOMAIN and "_dataset_" in (e.unique_id or "")
    ]
    assert dataset_entities == []
