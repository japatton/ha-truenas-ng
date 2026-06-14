"""Switch platform for the truenas_ng integration (services, apps, VMs)."""
from __future__ import annotations

from functools import partial

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TrueNASConfigEntry
from .client import TrueNASClient, TrueNASError
from .coordinator import AppsCoordinator, SystemCoordinator, VMsCoordinator
from .entity import (
    TrueNASEntity,
    app_device_info,
    hub_device_info,
    vm_device_info,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueNASConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up service / app / VM switches from a config entry."""
    data = entry.runtime_data
    entities: list[SwitchEntity] = []

    if data.enable_service_controls:
        entities.extend(
            TrueNASServiceSwitch(data.system, data.host_id, data.client, name)
            for name in data.system.data.services
        )
    if data.enable_apps:
        entities.extend(
            TrueNASAppSwitch(data.apps, data.host_id, data.client, name)
            for name in data.apps.data
        )
    if data.enable_vms:
        entities.extend(
            TrueNASVMSwitch(data.vms, data.host_id, data.client, vm_id)
            for vm_id in data.vms.data
        )
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


class TrueNASAppSwitch(TrueNASEntity[AppsCoordinator], SwitchEntity):
    """Start/stop a TrueNAS app via app.start / app.stop (primary entity of its device)."""

    _attr_name = None

    def __init__(
        self,
        coordinator: AppsCoordinator,
        host_id: str,
        client: TrueNASClient,
        name: str,
    ) -> None:
        """Initialize the switch for one app."""
        super().__init__(coordinator, host_id)
        self._client = client
        self._app = name
        self._attr_unique_id = f"{host_id}_app_{name}_switch"
        self._attr_device_info = app_device_info(host_id, coordinator.data[name])

    @property
    def available(self) -> bool:
        """Unavailable when the app leaves coordinator data."""
        return super().available and self._app in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return True when the app state is RUNNING."""
        app = self.coordinator.data.get(self._app)
        return None if app is None else app.get("state") == "RUNNING"

    async def _control(self, method: str) -> None:
        """Run app.start/app.stop on the executor and refresh."""
        try:
            await self.hass.async_add_executor_job(
                partial(self._client.call, method, self._app, job=True)
            )
        except TrueNASError as err:
            raise HomeAssistantError(
                f"Failed to {method} TrueNAS app {self._app}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        """Start the app."""
        await self._control("app.start")

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the app."""
        await self._control("app.stop")


class TrueNASVMSwitch(TrueNASEntity[VMsCoordinator], SwitchEntity):
    """Start/stop a TrueNAS VM via vm.start (non-job) / vm.stop (job)."""

    _attr_name = None

    def __init__(
        self,
        coordinator: VMsCoordinator,
        host_id: str,
        client: TrueNASClient,
        vm_id: int,
    ) -> None:
        """Initialize the switch for one VM."""
        super().__init__(coordinator, host_id)
        self._client = client
        self._vm_id = vm_id
        self._attr_unique_id = f"{host_id}_vm_{vm_id}_switch"
        self._attr_device_info = vm_device_info(host_id, coordinator.data[vm_id])

    @property
    def available(self) -> bool:
        """Unavailable when the VM leaves coordinator data."""
        return super().available and self._vm_id in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return True when the VM status.state is RUNNING."""
        vm = self.coordinator.data.get(self._vm_id)
        if vm is None:
            return None
        return (vm.get("status") or {}).get("state") == "RUNNING"

    async def _call(self, method: str, job: bool) -> None:
        """Run vm.start/vm.stop on the executor and refresh."""
        try:
            await self.hass.async_add_executor_job(
                partial(self._client.call, method, self._vm_id, job=job)
            )
        except TrueNASError as err:
            raise HomeAssistantError(
                f"Failed to {method} TrueNAS VM {self._vm_id}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        """Start the VM (vm.start is non-job)."""
        await self._call("vm.start", False)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the VM (vm.stop is a job)."""
        await self._call("vm.stop", True)
