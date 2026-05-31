"""Constants for the TrueNAS (Native) integration."""

from homeassistant.const import Platform

DOMAIN = "truenas_ng"
MANUFACTURER = "iXsystems"

DEFAULT_PORT = 9443
DEFAULT_USERNAME = "homeassistant"
DEFAULT_VERIFY_SSL = True

# Coordinator update intervals (seconds)
SCAN_INTERVAL_STORAGE = 30
SCAN_INTERVAL_DATASETS = 300
SCAN_INTERVAL_SYSTEM = 60
SCAN_INTERVAL_REPORTING = 20

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
