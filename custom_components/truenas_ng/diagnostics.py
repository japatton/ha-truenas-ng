"""Diagnostics support for the truenas_ng integration."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import TrueNASConfigEntry

TO_REDACT = {CONF_API_KEY, "serial"}


def _disks_by_name(disks: dict[str, dict]) -> dict[str, dict]:
    """F8: Re-key the disks mapping by disk name (devname) so raw serial strings
    don't appear as dict keys in the diagnostics output.  The coordinator keys
    disks by serial (or identifier/name fallback), which would leak the serial
    in the JSON keys even though async_redact_data redacts *values* named
    'serial'.  Using the devname as the key avoids that leak while still
    allowing the 'serial' value field to be redacted normally.
    """
    result: dict[str, dict] = {}
    for disk in disks.values():
        name = disk.get("name") or disk.get("devname")
        if name:
            result[name] = disk
    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TrueNASConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a TrueNAS config entry."""
    runtime = entry.runtime_data

    storage = runtime.storage.data
    system = runtime.system.data
    reporting = runtime.reporting.data

    storage_dict: dict[str, Any] | None = None
    if storage is not None:
        storage_dict = asdict(storage)
        # F8: re-key disks by devname so serial strings don't appear as keys
        storage_dict["disks"] = _disks_by_name(storage_dict["disks"])

    raw: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": dict(entry.data),
        },
        "storage": storage_dict,
        "system": asdict(system) if system is not None else None,
        "reporting": asdict(reporting) if reporting is not None else None,
        "datasets": runtime.datasets.data,
    }

    return async_redact_data(raw, TO_REDACT)
