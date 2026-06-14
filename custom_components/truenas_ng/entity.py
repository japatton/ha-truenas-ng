"""Base entity and device_info helpers for the TrueNAS (Native) integration."""
from __future__ import annotations

from typing import TypeVar

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, MANUFACTURER

_CoordT = TypeVar("_CoordT", bound=DataUpdateCoordinator)


class TrueNASEntity(CoordinatorEntity[_CoordT]):
    """Base class for all TrueNAS entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: _CoordT, host_id: str) -> None:
        """Initialize the entity and remember the hub's host_id."""
        super().__init__(coordinator)
        self._host_id = host_id


def hub_device_info(host_id: str, info: dict) -> DeviceInfo:
    """Build the DeviceInfo for the TrueNAS hub device."""
    return DeviceInfo(
        identifiers={(DOMAIN, host_id)},
        name=f"TrueNAS {info.get('hostname', '')}".strip(),
        manufacturer=MANUFACTURER,
        model=info.get("system_product") or "TrueNAS",
        sw_version=info.get("version"),
    )


def pool_device_info(host_id: str, pool: dict) -> DeviceInfo:
    """Build the DeviceInfo for a ZFS pool device, linked under the hub."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{host_id}_pool_{pool['guid']}")},
        name=f"Pool {pool['name']}",
        manufacturer=MANUFACTURER,
        model="ZFS Pool",
        via_device=(DOMAIN, host_id),
    )


def disk_device_info(host_id: str, disk: dict, stable_id: str | None = None) -> DeviceInfo:
    """Build the DeviceInfo for a physical disk device, linked under the hub.

    ``stable_id`` should be the key under which this disk lives in the
    coordinator's disks dict (serial → identifier → name fallback, F5).
    When omitted the same fallback is computed from the disk dict.
    """
    if stable_id is None:
        stable_id = (
            disk.get("serial") or disk.get("identifier") or disk.get("name") or ""
        )
    return DeviceInfo(
        identifiers={(DOMAIN, f"{host_id}_disk_{stable_id}")},
        name=f"Disk {disk.get('name', stable_id)}",
        manufacturer=MANUFACTURER,
        model=disk.get("model"),
        via_device=(DOMAIN, host_id),
    )


def app_device_info(host_id: str, app: dict) -> DeviceInfo:
    """Build the DeviceInfo for a TrueNAS app device, linked under the hub."""
    name = app.get("name", "")
    return DeviceInfo(
        identifiers={(DOMAIN, f"{host_id}_app_{name}")},
        name=f"App {name}",
        manufacturer=MANUFACTURER,
        model="TrueNAS App",
        sw_version=app.get("human_version"),
        via_device=(DOMAIN, host_id),
    )


def vm_device_info(host_id: str, vm: dict) -> DeviceInfo:
    """Build the DeviceInfo for a TrueNAS VM device, linked under the hub."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{host_id}_vm_{vm.get('id')}")},
        name=f"VM {vm.get('name', '')}",
        manufacturer=MANUFACTURER,
        model="TrueNAS VM",
        via_device=(DOMAIN, host_id),
    )
