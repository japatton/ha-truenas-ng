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
from .const import PLATFORMS
from .coordinator import (
    DatasetCoordinator,
    ReportingCoordinator,
    StorageCoordinator,
    SystemCoordinator,
)
from .repairs import async_setup_alert_issues

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

    storage = StorageCoordinator(hass, client)
    datasets = DatasetCoordinator(hass, client)
    system = SystemCoordinator(hass, client)
    reporting = ReportingCoordinator(hass, client, physmem)

    await storage.async_config_entry_first_refresh()
    await datasets.async_config_entry_first_refresh()
    await system.async_config_entry_first_refresh()
    await reporting.async_config_entry_first_refresh()

    entry.runtime_data = TrueNASRuntimeData(
        client=client,
        host_id=host_id,
        physmem=physmem,
        storage=storage,
        datasets=datasets,
        system=system,
        reporting=reporting,
    )

    async_setup_alert_issues(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TrueNASConfigEntry
) -> bool:
    """Unload a TrueNAS (Native) config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.async_add_executor_job(entry.runtime_data.client.close)
    return unload_ok
