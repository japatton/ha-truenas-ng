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
    """PLATFORMS lists exactly sensor, binary_sensor, button, switch (in order)."""
    assert const.PLATFORMS == [
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
        Platform.SWITCH,
    ]


def test_v02_option_keys_and_defaults() -> None:
    """v0.2 adds the update interval, option keys, and group defaults."""
    from custom_components.truenas_ng import const

    assert const.SCAN_INTERVAL_UPDATE == 21600
    assert const.MIN_SCAN_INTERVAL == 5

    # Option keys exist and are distinct strings.
    keys = {
        const.CONF_INTERVAL_STORAGE,
        const.CONF_INTERVAL_DATASETS,
        const.CONF_INTERVAL_SYSTEM,
        const.CONF_INTERVAL_REPORTING,
        const.CONF_INTERVAL_UPDATE,
        const.CONF_ENABLE_DATASETS,
        const.CONF_ENABLE_DISKS,
        const.CONF_ENABLE_REPORTING,
        const.CONF_ENABLE_SERVICE_CONTROLS,
    }
    assert len(keys) == 9

    # Group defaults: datasets off, everything else on.
    assert const.DEFAULT_ENABLE_DATASETS is False
    assert const.DEFAULT_ENABLE_DISKS is True
    assert const.DEFAULT_ENABLE_REPORTING is True
    assert const.DEFAULT_ENABLE_SERVICE_CONTROLS is True
