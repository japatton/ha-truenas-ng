"""Tests for the truenas_ng Repairs alert reconciliation and dismiss flow."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.truenas_ng.const import DOMAIN
from custom_components.truenas_ng.coordinator import SystemData
from custom_components.truenas_ng.repairs import (
    ALERT_TRANSLATION_KEY,
    async_create_fix_flow,
    async_sync_alert_issues,
)

CRITICAL_UUID = "f1b2c3d4-0000-1111-2222-333344445555"
NOTICE_UUID = "db72c8a1-a78a-4aa4-bb0b-2790ea6a086d"


async def test_issue_created_for_critical_alert_only(
    hass: HomeAssistant, init_integration
) -> None:
    """A fixable ERROR issue exists for the CRITICAL SMARTFailed alert, not the NOTICE one."""
    registry = ir.async_get(hass)

    issue = registry.async_get_issue(DOMAIN, CRITICAL_UUID)
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == ALERT_TRANSLATION_KEY
    assert issue.data == {"uuid": CRITICAL_UUID, "entry_id": init_integration.entry_id}

    assert registry.async_get_issue(DOMAIN, NOTICE_UUID) is None


async def test_issue_deleted_when_alert_clears(
    hass: HomeAssistant, init_integration
) -> None:
    """When the alert disappears from SystemData, its issue is removed on the next sync."""
    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, CRITICAL_UUID) is not None

    entry = init_integration
    system = entry.runtime_data.system
    system.data = SystemData(info=system.data.info, alerts=[], services=system.data.services)

    async_sync_alert_issues(hass, entry)

    assert registry.async_get_issue(DOMAIN, CRITICAL_UUID) is None


async def test_dismiss_fix_flow_calls_alert_dismiss(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """The confirm step dismisses the alert on the executor and clears the issue."""
    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, CRITICAL_UUID) is not None

    flow = await async_create_fix_flow(
        hass,
        CRITICAL_UUID,
        {"uuid": CRITICAL_UUID, "entry_id": init_integration.entry_id},
    )
    flow.hass = hass

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await flow.async_step_confirm({})
    assert result["type"] == "create_entry"

    mock_client.call.assert_any_call("alert.dismiss", CRITICAL_UUID)
    assert registry.async_get_issue(DOMAIN, CRITICAL_UUID) is None
