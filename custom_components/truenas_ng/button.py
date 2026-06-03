"""Button platform for the truenas_ng integration."""
from __future__ import annotations

from functools import partial

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TrueNASConfigEntry
from .client import TrueNASClient, TrueNASError
from .coordinator import StorageCoordinator, SystemCoordinator
from .entity import TrueNASEntity, hub_device_info, pool_device_info

REBOOT_REASON = "Initiated from Home Assistant"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueNASConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TrueNAS buttons from a config entry."""
    data = entry.runtime_data
    client = data.client
    host_id = data.host_id

    entities: list[ButtonEntity] = []

    for guid, pool in data.storage.data.pools.items():
        entities.append(
            TrueNASScrubButton(data.storage, host_id, client, guid, pool)
        )

    entities.append(
        TrueNASSystemButton(
            data.system,
            host_id,
            client,
            ButtonEntityDescription(
                key="reboot",
                translation_key="reboot",
                entity_category=EntityCategory.CONFIG,
                device_class=None,
            ),
            method="system.reboot",
        )
    )
    entities.append(
        TrueNASSystemButton(
            data.system,
            host_id,
            client,
            ButtonEntityDescription(
                key="shutdown",
                translation_key="shutdown",
                entity_category=EntityCategory.CONFIG,
                device_class=None,
            ),
            method="system.shutdown",
        )
    )

    if data.enable_service_controls:
        for name in data.system.data.services:
            entities.append(
                TrueNASServiceRestartButton(data.system, host_id, client, name)
            )

    async_add_entities(entities)


class TrueNASScrubButton(TrueNASEntity[StorageCoordinator], ButtonEntity):
    """Button that starts a ZFS scrub on a single pool."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "scrub"

    def __init__(
        self,
        coordinator: StorageCoordinator,
        host_id: str,
        client: TrueNASClient,
        guid: str,
        pool: dict,
    ) -> None:
        """Initialize the scrub button for one pool."""
        super().__init__(coordinator, host_id)
        self._client = client
        self._guid = guid
        self._pool_id = pool["id"]
        self._attr_unique_id = f"{host_id}_pool_{guid}_scrub"
        self._attr_device_info = pool_device_info(host_id, pool)

    async def async_press(self) -> None:
        """Start a scrub on this pool."""
        await self.hass.async_add_executor_job(
            partial(
                self._client.call,
                "pool.scrub",
                self._pool_id,
                "START",
                job=True,
            )
        )


class TrueNASSystemButton(TrueNASEntity[SystemCoordinator], ButtonEntity):
    """Button that runs a system-wide action (reboot / shutdown)."""

    def __init__(
        self,
        coordinator: SystemCoordinator,
        host_id: str,
        client: TrueNASClient,
        description: ButtonEntityDescription,
        method: str,
    ) -> None:
        """Initialize a system button."""
        super().__init__(coordinator, host_id)
        self.entity_description = description
        self._client = client
        self._method = method
        self._attr_unique_id = f"{host_id}_system_{description.key}"
        self._attr_device_info = hub_device_info(host_id, coordinator.data.info)

    async def async_press(self) -> None:
        """Invoke the system action."""
        await self.hass.async_add_executor_job(
            partial(
                self._client.call,
                self._method,
                REBOOT_REASON,
                job=True,
            )
        )


class TrueNASServiceRestartButton(TrueNASEntity[SystemCoordinator], ButtonEntity):
    """Restart a single TrueNAS system service via service.control."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "service_restart"

    def __init__(
        self,
        coordinator: SystemCoordinator,
        host_id: str,
        client: TrueNASClient,
        name: str,
    ) -> None:
        """Initialize the restart button for one service."""
        super().__init__(coordinator, host_id)
        self._client = client
        self._service = name
        self._attr_translation_placeholders = {"service": name}
        self._attr_unique_id = f"{host_id}_service_{name}_restart"
        self._attr_device_info = hub_device_info(host_id, coordinator.data.info)

    @property
    def available(self) -> bool:
        """Unavailable when the service vanishes from coordinator data."""
        return super().available and self._service in self.coordinator.data.services

    async def async_press(self) -> None:
        """Restart the service."""
        try:
            await self.hass.async_add_executor_job(
                partial(
                    self._client.call,
                    "service.control",
                    "RESTART",
                    self._service,
                    job=True,
                )
            )
        except TrueNASError as err:
            raise HomeAssistantError(
                f"Failed to restart TrueNAS service {self._service}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
