"""Switch platform for the truenas_ng integration (per-service start/stop)."""
from __future__ import annotations

from functools import partial

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TrueNASConfigEntry
from .client import TrueNASClient, TrueNASError
from .coordinator import SystemCoordinator
from .entity import TrueNASEntity, hub_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueNASConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up per-service control switches from a config entry."""
    data = entry.runtime_data
    if not data.enable_service_controls:
        return

    entities = [
        TrueNASServiceSwitch(data.system, data.host_id, data.client, name)
        for name in data.system.data.services
    ]
    async_add_entities(entities)


class TrueNASServiceSwitch(TrueNASEntity[SystemCoordinator], SwitchEntity):
    """Start/stop a TrueNAS system service via service.control."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "service_control"

    def __init__(
        self,
        coordinator: SystemCoordinator,
        host_id: str,
        client: TrueNASClient,
        name: str,
    ) -> None:
        """Initialize the switch for one service."""
        super().__init__(coordinator, host_id)
        self._client = client
        self._service = name
        self._attr_translation_placeholders = {"service": name}
        self._attr_unique_id = f"{host_id}_service_{name}_switch"
        self._attr_device_info = hub_device_info(host_id, coordinator.data.info)

    @property
    def available(self) -> bool:
        """Unavailable when the service vanishes from coordinator data."""
        return super().available and self._service in self.coordinator.data.services

    @property
    def is_on(self) -> bool | None:
        """Return True when the service state is RUNNING."""
        service = self.coordinator.data.services.get(self._service)
        if service is None:
            return None
        return service.get("state") == "RUNNING"

    async def _control(self, verb: str) -> None:
        """Run service.control on the executor and refresh state."""
        try:
            await self.hass.async_add_executor_job(
                partial(
                    self._client.call, "service.control", verb, self._service, job=True
                )
            )
        except TrueNASError as err:
            raise HomeAssistantError(
                f"Failed to {verb.lower()} TrueNAS service {self._service}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        """Start the service."""
        await self._control("START")

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the service."""
        await self._control("STOP")
