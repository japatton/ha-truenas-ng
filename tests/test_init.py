"""Tests for truenas_ng integration setup and unload."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.truenas_ng.client import TrueNASConnectionError
from custom_components.truenas_ng.const import DOMAIN

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

# Sensor/binary_sensor/button platform modules are not yet implemented.
# HA 2026.5.1 raises ModuleNotFoundError instead of skipping missing platforms,
# so we patch PLATFORMS to [] for all setup-based tests.
_EMPTY_PLATFORMS: list = []


@pytest.fixture
async def init_integration_no_platforms(
    hass: HomeAssistant, mock_client: MagicMock
) -> MockConfigEntry:
    """Set up the integration with mocked client and PLATFORMS patched to []."""
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
        patch("custom_components.truenas_ng.PLATFORMS", _EMPTY_PLATFORMS),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_setup_entry_loads(
    hass: HomeAssistant, init_integration_no_platforms: MockConfigEntry
) -> None:
    """A successful setup leaves the entry LOADED with populated runtime data."""
    entry = init_integration_no_platforms

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.host_id == HOST_ID
    assert entry.runtime_data.physmem == 65123586048
    assert entry.runtime_data.client is not None
    assert entry.runtime_data.storage.data is not None
    assert entry.runtime_data.system.data is not None
    assert entry.runtime_data.reporting.data is not None
    assert entry.runtime_data.datasets.data is not None


async def test_unload_entry(
    hass: HomeAssistant, init_integration_no_platforms: MockConfigEntry
) -> None:
    """Unloading a loaded entry succeeds, marks it NOT_LOADED, and closes the client."""
    entry = init_integration_no_platforms
    client = entry.runtime_data.client

    with patch("custom_components.truenas_ng.PLATFORMS", _EMPTY_PLATFORMS):
        assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    client.close.assert_called_once()


async def test_runtime_data_has_update_and_toggles(hass, init_integration) -> None:
    """Runtime data carries the UpdateCoordinator and group-toggle booleans."""
    from custom_components.truenas_ng.coordinator import UpdateCoordinator

    data = init_integration.runtime_data
    assert isinstance(data.update, UpdateCoordinator)
    assert data.update.data.installed_version == "26.0.0-BETA.1"

    # init_integration enables all groups via options.
    assert data.enable_datasets is True
    assert data.enable_disks is True
    assert data.enable_reporting is True
    assert data.enable_service_controls is True


async def test_options_update_reloads_entry(hass, init_integration) -> None:
    """Updating options triggers a reload via the update listener."""
    from custom_components.truenas_ng.const import CONF_ENABLE_DATASETS

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(
            init_integration, options={CONF_ENABLE_DATASETS: True}
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(init_integration.entry_id)


async def test_setup_entry_connection_error_retries(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """A connection failure during connect() yields SETUP_RETRY."""
    mock_client.connect.side_effect = TrueNASConnectionError("no route to host")
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

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.close.assert_called_once()


async def test_runtime_data_has_apps_and_vms(hass, init_integration) -> None:
    """Runtime data carries the Apps/VMs coordinators and default-on toggles."""
    from custom_components.truenas_ng.coordinator import (
        AppsCoordinator,
        VMsCoordinator,
    )

    data = init_integration.runtime_data
    assert isinstance(data.apps, AppsCoordinator)
    assert isinstance(data.vms, VMsCoordinator)
    assert set(data.apps.data) == {"radarr", "jellyfin", "sabnzbd"}
    assert set(data.vms.data) == {1, 2}
    assert data.enable_apps is True
    assert data.enable_vms is True
