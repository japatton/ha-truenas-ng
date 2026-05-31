"""Tests for truenas_ng constants (Shared Contract C1)."""
from homeassistant.const import Platform

from custom_components.truenas_ng import const


def test_domain_and_manufacturer() -> None:
    """DOMAIN and manufacturer string match the contract exactly."""
    assert const.DOMAIN == "truenas_ng"
    assert const.MANUFACTURER == "iXsystems"


def test_connection_defaults() -> None:
    """Default connection parameters match the contract."""
    assert const.DEFAULT_PORT == 9443
    assert const.DEFAULT_USERNAME == "homeassistant"
    assert const.DEFAULT_VERIFY_SSL is True


def test_scan_intervals() -> None:
    """Coordinator scan intervals (seconds) match the contract."""
    assert const.SCAN_INTERVAL_STORAGE == 30
    assert const.SCAN_INTERVAL_DATASETS == 300
    assert const.SCAN_INTERVAL_SYSTEM == 60
    assert const.SCAN_INTERVAL_REPORTING == 20


def test_platforms() -> None:
    """PLATFORMS lists exactly sensor, binary_sensor, button (in order)."""
    assert const.PLATFORMS == [
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
    ]
