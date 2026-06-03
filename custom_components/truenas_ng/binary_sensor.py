"""Binary sensor platform for the truenas_ng integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TrueNASConfigEntry
from .coordinator import StorageCoordinator, SystemCoordinator
from .entity import (
    TrueNASEntity,
    disk_device_info,
    hub_device_info,
    pool_device_info,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueNASConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up truenas_ng binary sensors from a config entry."""
    data = entry.runtime_data
    host_id = data.host_id
    storage = data.storage
    system = data.system

    entities: list[BinarySensorEntity] = []

    for guid in storage.data.pools:
        entities.append(TrueNASPoolHealthBinarySensor(storage, host_id, guid))

    if data.enable_disks:
        for stable_id in storage.data.disks:
            entities.append(
                TrueNASDiskProblemBinarySensor(storage, host_id, stable_id)
            )

    for name in system.data.services:
        entities.append(TrueNASServiceRunningBinarySensor(system, host_id, name))

    entities.append(TrueNASCriticalAlertBinarySensor(system, host_id))

    async_add_entities(entities)


class TrueNASPoolHealthBinarySensor(
    TrueNASEntity[StorageCoordinator], BinarySensorEntity
):
    """Reports a problem when a pool is not ONLINE or not healthy."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "pool_health"

    def __init__(
        self, coordinator: StorageCoordinator, host_id: str, guid: str
    ) -> None:
        """Initialize the pool health binary sensor."""
        super().__init__(coordinator, host_id)
        self._guid = guid
        self._attr_unique_id = f"{host_id}_pool_{guid}_health"
        self._attr_device_info = pool_device_info(
            host_id, coordinator.data.pools[guid]
        )

    @property
    def available(self) -> bool:
        """F7: unavailable (not unknown) when the pool vanishes from coordinator data."""
        return super().available and self._guid in self.coordinator.data.pools

    @property
    def is_on(self) -> bool | None:
        """Return True if the pool has a problem."""
        pool = self.coordinator.data.pools.get(self._guid)
        if pool is None:
            return None
        return pool.get("status") != "ONLINE" or not pool.get("healthy")


class TrueNASDiskProblemBinarySensor(
    TrueNASEntity[StorageCoordinator], BinarySensorEntity
):
    """Reports a problem when a disk's ZFS status or error counters are bad."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "disk_problem"

    def __init__(
        self, coordinator: StorageCoordinator, host_id: str, stable_id: str
    ) -> None:
        """Initialize the disk problem binary sensor."""
        super().__init__(coordinator, host_id)
        # F5: stable_id is the coordinator-dict key (serial → identifier → name)
        self._stable_id = stable_id
        self._attr_unique_id = f"{host_id}_disk_{stable_id}_problem"
        self._attr_device_info = disk_device_info(
            host_id, coordinator.data.disks[stable_id], stable_id
        )

    @property
    def available(self) -> bool:
        """F7: unavailable (not unknown) when the disk vanishes from coordinator data."""
        return super().available and self._stable_id in self.coordinator.data.disks

    @property
    def is_on(self) -> bool | None:
        """Return True if the disk has a ZFS problem or any error counter."""
        disk = self.coordinator.data.disks.get(self._stable_id)
        if disk is None:
            return None
        zfs_status = disk.get("zfs_status")
        if zfs_status is not None and zfs_status != "ONLINE":
            return True
        errors = disk.get("errors") or {}
        return (
            (errors.get("read") or 0) > 0
            or (errors.get("write") or 0) > 0
            or (errors.get("checksum") or 0) > 0
        )


class TrueNASServiceRunningBinarySensor(
    TrueNASEntity[SystemCoordinator], BinarySensorEntity
):
    """Reports whether a system service is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "service_running"

    def __init__(
        self, coordinator: SystemCoordinator, host_id: str, name: str
    ) -> None:
        """Initialize the service running binary sensor."""
        super().__init__(coordinator, host_id)
        self._service = name
        self._attr_translation_placeholders = {"service": name}
        self._attr_unique_id = f"{host_id}_service_{name}_running"
        self._attr_device_info = hub_device_info(host_id, coordinator.data.info)

    @property
    def available(self) -> bool:
        """F7: unavailable (not unknown) when the service vanishes from coordinator data."""
        return super().available and self._service in self.coordinator.data.services

    @property
    def is_on(self) -> bool | None:
        """Return True if the service state is RUNNING."""
        service = self.coordinator.data.services.get(self._service)
        if service is None:
            return None
        return service.get("state") == "RUNNING"


class TrueNASCriticalAlertBinarySensor(
    TrueNASEntity[SystemCoordinator], BinarySensorEntity
):
    """Reports a problem when any non-dismissed CRITICAL alert is present."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "alerts_critical"

    def __init__(self, coordinator: SystemCoordinator, host_id: str) -> None:
        """Initialize the critical alert binary sensor."""
        super().__init__(coordinator, host_id)
        self._attr_unique_id = f"{host_id}_alerts_critical"
        self._attr_device_info = hub_device_info(host_id, coordinator.data.info)

    @property
    def is_on(self) -> bool:
        """Return True if a non-dismissed CRITICAL alert exists."""
        return any(
            not alert.get("dismissed") and alert.get("level") == "CRITICAL"
            for alert in self.coordinator.data.alerts
        )
