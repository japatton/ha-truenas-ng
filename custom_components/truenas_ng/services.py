"""Integration services for truenas_ng: dismiss/restore TrueNAS alerts."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .client import TrueNASError
from .const import DOMAIN

SERVICE_DISMISS_ALERT = "dismiss_alert"
SERVICE_RESTORE_ALERT = "restore_alert"
ATTR_UUID = "uuid"
ATTR_ENTRY_ID = "entry_id"

_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_UUID): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)


def _resolve_entry(hass: HomeAssistant, call: ServiceCall):
    """Return the target loaded config entry, or raise ServiceValidationError."""
    entry_id = call.data.get(ATTR_ENTRY_ID)
    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if entry_id is not None:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or entry not in loaded:
            raise ServiceValidationError(
                f"No loaded TrueNAS config entry with id {entry_id}"
            )
        return entry
    if not loaded:
        raise ServiceValidationError("No loaded TrueNAS config entry")
    if len(loaded) > 1:
        raise ServiceValidationError(
            "Multiple TrueNAS config entries are loaded; specify entry_id"
        )
    return loaded[0]


async def _async_alert_action(hass: HomeAssistant, call: ServiceCall, method: str) -> None:
    """Run alert.dismiss/alert.restore on the executor, then refresh alerts."""
    entry = _resolve_entry(hass, call)
    client = entry.runtime_data.client
    uuid = call.data[ATTR_UUID]
    try:
        await hass.async_add_executor_job(client.call, method, uuid)
    except TrueNASError as err:
        raise HomeAssistantError(f"TrueNAS {method} failed: {err}") from err
    await entry.runtime_data.system.async_request_refresh()


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the dismiss/restore services once for the integration."""
    if hass.services.has_service(DOMAIN, SERVICE_DISMISS_ALERT):
        return

    async def _dismiss(call: ServiceCall) -> None:
        await _async_alert_action(hass, call, "alert.dismiss")

    async def _restore(call: ServiceCall) -> None:
        await _async_alert_action(hass, call, "alert.restore")

    hass.services.async_register(
        DOMAIN, SERVICE_DISMISS_ALERT, _dismiss, schema=_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE_ALERT, _restore, schema=_SERVICE_SCHEMA
    )


@callback
def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove the services once no TrueNAS entries remain loaded."""
    # When called from async_unload_entry, HA has already moved the entry being
    # unloaded to UNLOAD_IN_PROGRESS, so it does not count as LOADED here.
    still_loaded = any(
        entry.state is ConfigEntryState.LOADED
        for entry in hass.config_entries.async_entries(DOMAIN)
    )
    if still_loaded:
        return
    hass.services.async_remove(DOMAIN, SERVICE_DISMISS_ALERT)
    hass.services.async_remove(DOMAIN, SERVICE_RESTORE_ALERT)
