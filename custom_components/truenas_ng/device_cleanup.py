"""Drop the devices of TrueNAS apps and VMs that are gone.

TrueNAS reports only what exists now, so without this a removed app's or VM's
device would stay in Home Assistant, unavailable, with no way to delete it. App
and VM devices go once TrueNAS stops listing them; any child device TrueNAS no
longer reports (a replaced disk, an exported pool) can be deleted from its device
page.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

if TYPE_CHECKING:
    from . import TrueNASConfigEntry, TrueNASRuntimeData
    from .coordinator import AppsCoordinator, VMsCoordinator

_LOGGER = logging.getLogger(__name__)

CHILD_KINDS = ("pool", "disk", "app", "vm")

# How many answered, non-empty listings in a row must leave a device out before
# it goes.
STALE_LISTINGS = 2


def child_identity(host_id: str, device: dr.DeviceEntry) -> tuple[str, str] | None:
    """Return (kind, key) when the device is one of this hub's child devices.

    Child identifiers are ``f"{host_id}_{kind}_{key}"``, with kind pool, disk, app
    or vm (see entity.py). The hub's own identifier is the bare host_id.
    """
    prefix = f"{host_id}_"
    for domain, identifier in device.identifiers:
        if domain != DOMAIN or not identifier.startswith(prefix):
            continue
        kind, sep, key = identifier.removeprefix(prefix).partition("_")
        if sep and kind in CHILD_KINDS:
            return kind, key
    return None


def _listed(coordinator: AppsCoordinator | VMsCoordinator) -> set[str] | None:
    """Keys in the coordinator's last listing, or None if TrueNAS didn't answer."""
    if not coordinator.last_update_success or not coordinator.listing_ok:
        return None
    return {str(key) for key in coordinator.data}


def reported_keys(data: TrueNASRuntimeData, kind: str) -> set[str] | None:
    """Keys TrueNAS reports now for one kind of child device; None when unknown."""
    if kind == "app":
        return _listed(data.apps)
    if kind == "vm":
        return _listed(data.vms)
    storage = data.storage
    if not storage.last_update_success or storage.data is None:
        return None
    if kind == "pool":
        return {str(guid) for guid in storage.data.pools}
    return {str(stable_id) for stable_id in storage.data.disks}


def device_is_removable(data: TrueNASRuntimeData, device: dr.DeviceEntry) -> bool:
    """Whether a user may delete this device: never the hub, nor a reported child."""
    if (DOMAIN, data.host_id) in device.identifiers:
        return False
    identity = child_identity(data.host_id, device)
    if identity is None:
        # Not a device this entry creates now (one left by an older host id, say),
        # so nothing would add it back.
        return True
    kind, key = identity
    reported = reported_keys(data, kind)
    return reported is not None and key not in reported


class RemovedDeviceCleaner:
    """Drop the app or VM devices that TrueNAS no longer lists.

    A device goes once STALE_LISTINGS answered, non-empty listings in a row leave
    it out, and its entities go with it. An unanswered listing doesn't count
    either way. Neither does an empty one: that is likelier the apps or VMs still
    starting after a NAS boot than every one of them removed, and a device dropped
    by mistake would only come back on the next reload.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TrueNASConfigEntry,
        coordinator: AppsCoordinator | VMsCoordinator,
        kind: str,
    ) -> None:
        """Watch one coordinator's listing for one kind of child device."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._kind = kind
        self._misses: dict[str, int] = {}

    @callback
    def async_check(self) -> None:
        """Count the devices this listing leaves out; remove those left out enough."""
        listed = _listed(self._coordinator)
        if not listed:
            return
        host_id = self._entry.runtime_data.host_id
        registry = dr.async_get(self._hass)
        misses: dict[str, int] = {}
        for device in dr.async_entries_for_config_entry(registry, self._entry.entry_id):
            identity = child_identity(host_id, device)
            if identity is None or identity[0] != self._kind or identity[1] in listed:
                continue
            count = self._misses.get(device.id, 0) + 1
            if count < STALE_LISTINGS:
                misses[device.id] = count
                continue
            _LOGGER.info(
                "Removing device %s: TrueNAS no longer lists it",
                device.name_by_user or device.name,
            )
            registry.async_remove_device(device.id)
        self._misses = misses
