"""Self-tests for the shared pytest harness (Shared Contract C6)."""
import json

import pytest
from unittest.mock import MagicMock


def test_mock_client_is_sync_magicmock(mock_client: MagicMock) -> None:
    """The mock client is a plain MagicMock (NOT async)."""
    assert isinstance(mock_client, MagicMock)
    assert mock_client.ping() is True
    # connect/close are no-ops that must not raise.
    assert mock_client.connect() is None
    assert mock_client.close() is None


def test_call_dispatches_known_methods_to_fixtures(mock_client: MagicMock) -> None:
    """.call routes each known method name to its C7 fixture payload."""
    # host_id.json is a bare JSON string.
    assert (
        mock_client.call("system.host_id")
        == "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    info = mock_client.call("system.info")
    assert info["hostname"] == "truenas"
    assert info["physmem"] == 65123586048

    pools = mock_client.call("pool.query")
    assert {p["name"] for p in pools} == {"Data", "Virtualization"}

    disks = mock_client.call("disk.query")
    assert {d["serial"] for d in disks} == {
        "NVMEFAKESERIAL01",
        "WD-DEADBEEF01",
        "USB-SSD-77",
    }

    temps = mock_client.call("disk.temperatures")
    assert temps["sda"] == 37.0
    assert temps["sdc"] is None

    services = mock_client.call("service.query")
    assert {s["service"] for s in services} == {"cifs", "ssh", "nfs"}

    alerts = mock_client.call("alert.list")
    assert {a["level"] for a in alerts} == {"NOTICE", "CRITICAL"}

    datasets = mock_client.call("pool.dataset.query")
    assert datasets[0]["id"] == "Data"

    reporting = mock_client.call("reporting.get_data")
    assert [g["name"] for g in reporting] == ["cpu", "cputemp", "memory"]


def test_call_returns_none_for_action_methods(mock_client: MagicMock) -> None:
    """Action RPCs (scrub/reboot/shutdown/dismiss) return None."""
    assert mock_client.call("pool.scrub", "Data") is None
    assert mock_client.call("system.reboot") is None
    assert mock_client.call("system.shutdown") is None
    assert mock_client.call("alert.dismiss", "uuid") is None


def test_call_rejects_unknown_method(mock_client: MagicMock) -> None:
    """An unmapped method name raises AssertionError (catches typos in tests)."""
    with pytest.raises(AssertionError):
        mock_client.call("not.a.real.method")


def test_reporting_fixture_derived_values(mock_client: MagicMock) -> None:
    """The C7 reporting payload yields the contract's promised derived values."""
    cpu, cputemp, memory = mock_client.call("reporting.get_data")
    assert cpu["data"][-1][cpu["legend"].index("cpu")] == 2
    last_temp_row = cputemp["data"][-1][1:]
    assert sum(last_temp_row) / len(last_temp_row) == 46.0
    physmem = mock_client.call("system.info")["physmem"]
    free = memory["data"][-1][memory["legend"].index("available")]
    assert free == 30234440000
    assert physmem - free == 34889146048
    assert round((physmem - free) / physmem * 100, 1) == 53.6
