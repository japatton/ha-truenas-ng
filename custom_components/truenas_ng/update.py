"""Update platform for the truenas_ng integration (TrueNAS OS updates)."""
from __future__ import annotations

import logging
from functools import partial
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TrueNASConfigEntry
from .client import TrueNASClient, TrueNASError
from .coordinator import UpdateCoordinator
from .entity import TrueNASEntity, hub_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueNASConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TrueNAS OS update entity from a config entry."""
    data = entry.runtime_data
    async_add_entities(
        [
            TrueNASUpdateEntity(
                data.update, data.host_id, data.client, data.system.data.info
            )
        ]
    )


class TrueNASUpdateEntity(TrueNASEntity[UpdateCoordinator], UpdateEntity):
    """Represents the installable TrueNAS OS update on the hub device."""

    _attr_translation_key = "os_update"
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(
        self,
        coordinator: UpdateCoordinator,
        host_id: str,
        client: TrueNASClient,
        info: dict,
    ) -> None:
        """Initialize the OS update entity."""
        super().__init__(coordinator, host_id)
        self._client = client
        self._attr_unique_id = f"{host_id}_os_update"
        self._attr_device_info = hub_device_info(host_id, info)

    @property
    def installed_version(self) -> str | None:
        """The OS version currently running."""
        return self.coordinator.data.installed_version

    @property
    def latest_version(self) -> str | None:
        """The latest available OS version (== installed when up to date)."""
        return self.coordinator.data.latest_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Download and apply the update; the box reboots, dropping the socket."""
        try:
            await self.hass.async_add_executor_job(
                partial(self._client.call, "update.run", job=True)
            )
        except TrueNASError as err:
            # update.run downloads, creates a boot environment, then reboots,
            # which tears down the WebSocket mid-job. Treat that as the update
            # being underway rather than a failure.
            _LOGGER.warning(
                "TrueNAS update started; the system is likely rebooting (%s)", err
            )
