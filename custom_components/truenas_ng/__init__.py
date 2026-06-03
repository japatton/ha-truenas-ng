"""The TrueNAS (Native) integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .client import TrueNASAuthError, TrueNASClient, TrueNASError
from .const import (
    CONF_ENABLE_DATASETS,
    CONF_ENABLE_DISKS,
    CONF_ENABLE_REPORTING,
    CONF_ENABLE_SERVICE_CONTROLS,
    CONF_INTERVAL_DATASETS,
    CONF_INTERVAL_REPORTING,
    CONF_INTERVAL_STORAGE,
    CONF_INTERVAL_SYSTEM,
    CONF_INTERVAL_UPDATE,
    DEFAULT_ENABLE_DATASETS,
    DEFAULT_ENABLE_DISKS,
    DEFAULT_ENABLE_REPORTING,
    DEFAULT_ENABLE_SERVICE_CONTROLS,
    PLATFORMS,
    SCAN_INTERVAL_DATASETS,
    SCAN_INTERVAL_REPORTING,
    SCAN_INTERVAL_STORAGE,
    SCAN_INTERVAL_SYSTEM,
    SCAN_INTERVAL_UPDATE,
)
from .coordinator import (
    DatasetCoordinator,
    ReportingCoordinator,
    StorageCoordinator,
    SystemCoordinator,
    UpdateCoordinator,
)
from .repairs import async_setup_alert_issues
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)


@dataclass
class TrueNASRuntimeData:
    """Runtime data stored on the config entry."""

    client: TrueNASClient
    host_id: str
    physmem: int
    storage: StorageCoordinator
    datasets: DatasetCoordinator
    system: SystemCoordinator
    reporting: ReportingCoordinator
    update: UpdateCoordinator
    enable_datasets: bool
    enable_disks: bool
    enable_reporting: bool
    enable_service_controls: bool


type TrueNASConfigEntry = ConfigEntry[TrueNASRuntimeData]


def _connect_and_identify(client: TrueNASClient) -> tuple[dict, str]:
    """Connect, then fetch system.info and system.host_id (runs on the executor)."""
    client.connect()
    info = client.call("system.info")
    host_id = client.call("system.host_id")
    return info, host_id


async def async_setup_entry(
    hass: HomeAssistant, entry: TrueNASConfigEntry
) -> bool:
    """Set up TrueNAS (Native) from a config entry."""
    data = entry.data
    client = TrueNASClient(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        api_key=data[CONF_API_KEY],
        verify_ssl=data[CONF_VERIFY_SSL],
    )

    try:
        info, host_id = await hass.async_add_executor_job(
            _connect_and_identify, client
        )
    except TrueNASAuthError as err:
        await hass.async_add_executor_job(client.close)
        raise ConfigEntryAuthFailed(str(err)) from err
    except TrueNASError as err:
        await hass.async_add_executor_job(client.close)
        raise ConfigEntryNotReady(str(err)) from err

    physmem = info["physmem"]
    opts = entry.options

    storage = StorageCoordinator(
        hass, client, opts.get(CONF_INTERVAL_STORAGE, SCAN_INTERVAL_STORAGE)
    )
    datasets = DatasetCoordinator(
        hass, client, opts.get(CONF_INTERVAL_DATASETS, SCAN_INTERVAL_DATASETS)
    )
    system = SystemCoordinator(
        hass, client, opts.get(CONF_INTERVAL_SYSTEM, SCAN_INTERVAL_SYSTEM)
    )
    reporting = ReportingCoordinator(
        hass, client, physmem, opts.get(CONF_INTERVAL_REPORTING, SCAN_INTERVAL_REPORTING)
    )
    update = UpdateCoordinator(
        hass, client, opts.get(CONF_INTERVAL_UPDATE, SCAN_INTERVAL_UPDATE)
    )

    await storage.async_config_entry_first_refresh()
    await datasets.async_config_entry_first_refresh()
    await system.async_config_entry_first_refresh()
    await reporting.async_config_entry_first_refresh()
    await update.async_config_entry_first_refresh()

    entry.runtime_data = TrueNASRuntimeData(
        client=client,
        host_id=host_id,
        physmem=physmem,
        storage=storage,
        datasets=datasets,
        system=system,
        reporting=reporting,
        update=update,
        enable_datasets=opts.get(CONF_ENABLE_DATASETS, DEFAULT_ENABLE_DATASETS),
        enable_disks=opts.get(CONF_ENABLE_DISKS, DEFAULT_ENABLE_DISKS),
        enable_reporting=opts.get(CONF_ENABLE_REPORTING, DEFAULT_ENABLE_REPORTING),
        enable_service_controls=opts.get(
            CONF_ENABLE_SERVICE_CONTROLS, DEFAULT_ENABLE_SERVICE_CONTROLS
        ),
    )

    async_setup_alert_issues(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: TrueNASConfigEntry
) -> None:
    """Reload the entry when options change so new intervals/toggles take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: TrueNASConfigEntry
) -> bool:
    """Unload a TrueNAS (Native) config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.async_add_executor_job(entry.runtime_data.client.close)
        async_unregister_services(hass)
    return unload_ok
