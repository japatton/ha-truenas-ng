"""Repairs: reconcile TrueNAS alerts into the Home Assistant issue registry."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ALERT_TRANSLATION_KEY = "truenas_alert"

# Alert levels that warrant a Repairs issue, mapped to issue-registry severity.
_SEVERITY_BY_LEVEL: dict[str, ir.IssueSeverity] = {
    "WARNING": ir.IssueSeverity.WARNING,
    "CRITICAL": ir.IssueSeverity.ERROR,
}


@callback
def async_sync_alert_issues(hass: HomeAssistant, entry: Any) -> None:
    """Reconcile issue-registry entries against the System coordinator's alerts.

    Creates a fixable issue per non-dismissed WARNING/CRITICAL alert and deletes any
    previously-created issue whose alert is no longer present.
    """
    system_data = entry.runtime_data.system.data
    alerts = system_data.alerts if system_data is not None else []

    wanted: dict[str, dict] = {}
    for alert in alerts:
        if alert.get("dismissed"):
            continue
        severity = _SEVERITY_BY_LEVEL.get(alert.get("level"))
        if severity is None:
            continue
        uuid = alert.get("uuid")
        if not uuid:
            continue
        wanted[uuid] = alert

    registry = ir.async_get(hass)
    existing = {
        issue_id
        for (domain, issue_id), issue in registry.issues.items()
        if domain == DOMAIN
        and issue.translation_key == ALERT_TRANSLATION_KEY
        and issue.data is not None
        and issue.data.get("entry_id") == entry.entry_id
    }

    for uuid, alert in wanted.items():
        ir.async_create_issue(
            hass,
            DOMAIN,
            uuid,
            is_fixable=True,
            severity=_SEVERITY_BY_LEVEL[alert["level"]],
            translation_key=ALERT_TRANSLATION_KEY,
            translation_placeholders={
                "alert": alert.get("formatted") or alert.get("text") or uuid,
                "klass": alert.get("klass", ""),
            },
            data={"uuid": uuid, "entry_id": entry.entry_id},
        )

    for uuid in existing - wanted.keys():
        ir.async_delete_issue(hass, DOMAIN, uuid)


@callback
def async_setup_alert_issues(hass: HomeAssistant, entry: Any) -> None:
    """Wire alert reconciliation: sync once now, then on every System coordinator update."""

    @callback
    def _handle_update() -> None:
        async_sync_alert_issues(hass, entry)

    entry.async_on_unload(entry.runtime_data.system.async_add_listener(_handle_update))
    async_sync_alert_issues(hass, entry)


class TrueNASAlertRepairsFlow(RepairsFlow):
    """Confirm flow that dismisses a TrueNAS alert and removes its issue."""

    def __init__(self, entry_id: str, uuid: str) -> None:
        """Store the owning config entry id and the alert uuid to dismiss."""
        self._entry_id = entry_id
        self._uuid = uuid

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step — show the confirmation form."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dismiss the alert on the executor and delete the issue on confirmation."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry is not None and entry.runtime_data is not None:
                client = entry.runtime_data.client
                await self.hass.async_add_executor_job(
                    client.call, "alert.dismiss", self._uuid
                )
            ir.async_delete_issue(self.hass, DOMAIN, self._uuid)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Return the dismiss fix flow for a TrueNAS alert issue."""
    payload = data or {}
    return TrueNASAlertRepairsFlow(
        entry_id=payload.get("entry_id", ""),
        uuid=payload.get("uuid", issue_id),
    )
