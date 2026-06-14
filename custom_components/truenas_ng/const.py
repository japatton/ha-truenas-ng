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
SCAN_INTERVAL_UPDATE = 21600  # 6 h — OS updates change rarely
SCAN_INTERVAL_APPS = 60
SCAN_INTERVAL_VMS = 60

# Minimum poll interval the options flow will accept (seconds)
MIN_SCAN_INTERVAL = 5

# --- Options flow keys (stored in entry.options) ---
CONF_INTERVAL_STORAGE = "interval_storage"
CONF_INTERVAL_DATASETS = "interval_datasets"
CONF_INTERVAL_SYSTEM = "interval_system"
CONF_INTERVAL_REPORTING = "interval_reporting"
CONF_INTERVAL_UPDATE = "interval_update"
CONF_INTERVAL_APPS = "interval_apps"
CONF_INTERVAL_VMS = "interval_vms"

CONF_ENABLE_DATASETS = "enable_datasets"
CONF_ENABLE_DISKS = "enable_disks"
CONF_ENABLE_REPORTING = "enable_reporting"
CONF_ENABLE_SERVICE_CONTROLS = "enable_service_controls"
CONF_ENABLE_APPS = "enable_apps"
CONF_ENABLE_VMS = "enable_vms"

# Group enable defaults — datasets are heavy, so off by default.
DEFAULT_ENABLE_DATASETS = False
DEFAULT_ENABLE_DISKS = True
DEFAULT_ENABLE_REPORTING = True
DEFAULT_ENABLE_SERVICE_CONTROLS = True
DEFAULT_ENABLE_APPS = True
DEFAULT_ENABLE_VMS = True

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.UPDATE,
]
