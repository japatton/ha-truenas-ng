"""Tests for the truenas_ng coordinators."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.truenas_ng.client import (
    TrueNASAuthError,
    TrueNASConnectionError,
)
from custom_components.truenas_ng.coordinator import (
    DatasetCoordinator,
    ReportingCoordinator,
    StorageCoordinator,
    SystemCoordinator,
    TrueNASBaseCoordinator,
)


class _AuthFailCoordinator(TrueNASBaseCoordinator):
    """Coordinator whose fetch always raises an auth error."""

    def _fetch(self):
        raise TrueNASAuthError("bad key")


class _ConnFailCoordinator(TrueNASBaseCoordinator):
    """Coordinator whose fetch always raises a connection error."""

    def _fetch(self):
        raise TrueNASConnectionError("dropped")


async def test_base_maps_auth_error_to_config_entry_auth_failed(
    hass: HomeAssistant, mock_client
) -> None:
    """A TrueNASAuthError from _fetch becomes ConfigEntryAuthFailed."""
    coordinator = _AuthFailCoordinator(hass, mock_client, "auth", 30)
    with pytest.raises(ConfigEntryAuthFailed, match="bad key"):
        await coordinator._async_update_data()


async def test_base_maps_truenas_error_to_update_failed(
    hass: HomeAssistant, mock_client
) -> None:
    """A non-auth TrueNASError from _fetch becomes UpdateFailed."""
    coordinator = _ConnFailCoordinator(hass, mock_client, "conn", 30)
    with pytest.raises(UpdateFailed, match="dropped"):
        await coordinator._async_update_data()


async def test_storage_fetch_builds_pools_and_disks(
    hass: HomeAssistant, mock_client
) -> None:
    """StorageCoordinator keys pools by guid, disks by serial, injects temps/errors."""
    coordinator = StorageCoordinator(hass, mock_client)
    data = coordinator._fetch()

    # Pools keyed by guid.
    assert "1111111111111111111" in data.pools
    assert data.pools["1111111111111111111"]["status"] == "ONLINE"
    assert data.pools["1111111111111111111"]["name"] == "Data"

    # Disks keyed by serial; locate the "sda" disk by its name.
    sda = next(d for d in data.disks.values() if d["name"] == "sda")
    assert sda["serial"] == "WD-DEADBEEF01"
    assert sda["temperature"] == 37.0
    assert sda["errors"] == {"read": 0, "write": 0, "checksum": 0}
    assert sda["zfs_status"] == "ONLINE"

    # The USB-SSD ("sdc") is unassigned: no topology leaf -> zfs_status None,
    # temperature passes through as None.
    sdc = next(d for d in data.disks.values() if d["name"] == "sdc")
    assert sdc["zfs_status"] is None
    assert sdc["temperature"] is None
    assert sdc["errors"] == {"read": 0, "write": 0, "checksum": 0}


async def test_dataset_fetch_flattens_children(
    hass: HomeAssistant, mock_client
) -> None:
    """DatasetCoordinator flattens nested children and keeps snapshot_count."""
    coordinator = DatasetCoordinator(hass, mock_client)
    data = coordinator._fetch()

    assert set(data) == {"Data", "Data/media"}
    assert data["Data"]["snapshot_count"] == 0
    assert data["Data/media"]["snapshot_count"] == 3
    # Flattened child is present as a top-level key, not buried in children.
    assert data["Data/media"]["pool"] == "Data"


async def test_system_fetch_keys_services_by_name(
    hass: HomeAssistant, mock_client
) -> None:
    """SystemCoordinator returns info, alerts, and services keyed by service name."""
    coordinator = SystemCoordinator(hass, mock_client)
    data = coordinator._fetch()

    assert data.info["hostname"] == "truenas"
    assert len(data.alerts) == 2
    assert "cifs" in data.services
    assert data.services["cifs"]["state"] == "RUNNING"
    assert data.services["nfs"]["state"] == "STOPPED"


async def test_reporting_fetch_extracts_metrics(
    hass: HomeAssistant, mock_client
) -> None:
    """ReportingCoordinator derives cpu/memory metrics from the graph payload."""
    coordinator = ReportingCoordinator(hass, mock_client, physmem=65123586048)
    data = coordinator._fetch()

    assert data.cpu_percent == 2
    assert data.cpu_temp == 46.0
    assert data.memory_free == 30234440000
    assert data.memory_used == 34889146048
    assert data.memory_used_percent == 53.6


async def test_reporting_cpu_temp_with_none_values(
    hass: HomeAssistant, mock_client
) -> None:
    """F1: cpu_temp averaging must silently skip None entries (netdata null temps).

    A cputemp graph whose last row contains a None value must yield a numeric
    cpu_temp without raising TypeError.  If ALL values are None, cpu_temp must
    be None (not an error).
    """
    from unittest.mock import MagicMock

    # Inline client that returns a custom reporting payload with one None temp
    reporting_payload = [
        {
            "name": "cpu",
            "legend": ["time", "cpu"],
            "data": [[1, 5]],
        },
        {
            "name": "cputemp",
            "legend": ["time", "0", "1"],
            # Last row: core 0 is None, core 1 is 50.0
            "data": [[1, None, 50.0]],
        },
        {
            "name": "memory",
            "legend": ["time", "available"],
            "data": [[1, 1_000_000_000]],
        },
    ]

    def _call(method, *args, **kwargs):
        if method == "reporting.get_data":
            return reporting_payload
        return mock_client.call.side_effect(method, *args, **kwargs)

    patched = MagicMock()
    patched.call.side_effect = _call

    coordinator = ReportingCoordinator(hass, patched, physmem=8_000_000_000)
    data = coordinator._fetch()

    # Only the non-None value (50.0) contributes → average is 50.0
    assert data.cpu_temp == 50.0

    # Now test all-None: cpu_temp must be None, not raise
    reporting_payload[1]["data"] = [[1, None, None]]
    data2 = coordinator._fetch()
    assert data2.cpu_temp is None


async def test_storage_disk_without_serial(
    hass: HomeAssistant, mock_client
) -> None:
    """F5: a disk dict missing 'serial' must not raise KeyError.

    The coordinator should fall back to 'identifier' then 'name' as the
    stable_id.  The disk must still appear in data.disks keyed by the
    fallback id.
    """
    from unittest.mock import MagicMock

    # Inline disk list: one normal disk (has serial) + one without serial
    disk_payload = [
        {
            "name": "sda",
            "devname": "sda",
            "serial": "NORMAL-SERIAL-01",
            "model": "Normal Disk",
            "size": 1_000_000_000,
            "pool": None,
        },
        {
            "name": "sdb",
            "devname": "sdb",
            # 'serial' key is intentionally absent — simulates USB/virtual disk
            "identifier": "usb-ident-42",
            "model": "Virtual Disk",
            "size": 500_000_000,
            "pool": None,
        },
        {
            "name": "sdc",
            "devname": "sdc",
            # Both serial and identifier absent — falls back to name
            "model": "Mystery Disk",
            "size": 250_000_000,
            "pool": None,
        },
    ]

    def _call(method, *args, **kwargs):
        if method == "disk.query":
            return disk_payload
        if method == "disk.temperatures":
            return {}
        if method == "pool.query":
            return []
        return mock_client.call.side_effect(method, *args, **kwargs)

    patched = MagicMock()
    patched.call.side_effect = _call

    coordinator = StorageCoordinator(hass, patched)
    # Must not raise KeyError or TypeError
    data = coordinator._fetch()

    # sda keyed by its serial
    assert "NORMAL-SERIAL-01" in data.disks
    # sdb keyed by identifier (no serial)
    assert "usb-ident-42" in data.disks
    # sdc keyed by name (no serial, no identifier)
    assert "sdc" in data.disks
    # All three disks present
    assert len(data.disks) == 3


async def test_update_coordinator_up_to_date(hass, mock_client) -> None:
    """UpdateCoordinator reports installed==latest when status.new_version is null."""
    from custom_components.truenas_ng.coordinator import UpdateCoordinator

    coordinator = UpdateCoordinator(hass, mock_client)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data.installed_version == "26.0.0-BETA.1"
    assert coordinator.data.latest_version == "26.0.0-BETA.1"


def test_extract_new_version_handles_shapes() -> None:
    """_extract_new_version copes with null, str, and dict new_version nodes."""
    from custom_components.truenas_ng.coordinator import _extract_new_version

    assert _extract_new_version(None) is None
    assert _extract_new_version("") is None
    assert _extract_new_version("26.0.1") == "26.0.1"
    assert _extract_new_version({"version": "26.0.1"}) == "26.0.1"
    assert _extract_new_version({"name": "26.0.1-RC"}) == "26.0.1-RC"
    assert _extract_new_version({"unexpected": True}) is None


async def test_storage_coordinator_interval_override(hass, mock_client) -> None:
    """An explicit interval overrides the const default."""
    from datetime import timedelta

    from custom_components.truenas_ng.coordinator import StorageCoordinator

    coordinator = StorageCoordinator(hass, mock_client, 45)
    assert coordinator.update_interval == timedelta(seconds=45)


async def test_apps_coordinator_parses(hass, mock_client) -> None:
    """AppsCoordinator keys apps by name."""
    from custom_components.truenas_ng.coordinator import AppsCoordinator

    coordinator = AppsCoordinator(hass, mock_client)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert set(coordinator.data) == {"radarr", "jellyfin", "sabnzbd"}
    assert coordinator.data["radarr"]["upgrade_available"] is True


async def test_vms_coordinator_parses(hass, mock_client) -> None:
    """VMsCoordinator keys VMs by integer id."""
    from custom_components.truenas_ng.coordinator import VMsCoordinator

    coordinator = VMsCoordinator(hass, mock_client)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert set(coordinator.data) == {1, 2}
    assert coordinator.data[1]["status"]["state"] == "RUNNING"


async def test_apps_coordinator_graceful_on_error(hass, mock_client) -> None:
    """A failing app.query yields empty data, not a coordinator failure."""
    from custom_components.truenas_ng.client import TrueNASError
    from custom_components.truenas_ng.coordinator import AppsCoordinator

    def _boom(method, *args, **kwargs):
        if method == "app.query":
            raise TrueNASError("apps not configured")
        raise AssertionError(method)

    mock_client.call.side_effect = _boom
    coordinator = AppsCoordinator(hass, mock_client)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data == {}
