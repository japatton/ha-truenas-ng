"""Tests for the truenas_ng alert dismiss/restore services."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.truenas_ng.const import DOMAIN

UUID = "11111111-2222-3333-4444-555555555555"


async def test_services_registered(hass: HomeAssistant, init_integration) -> None:
    """Both services are registered once the integration is set up."""
    assert hass.services.has_service(DOMAIN, "dismiss_alert")
    assert hass.services.has_service(DOMAIN, "restore_alert")


async def test_dismiss_alert_calls_client(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """dismiss_alert calls alert.dismiss with the uuid."""
    mock_client.call.reset_mock()
    await hass.services.async_call(
        DOMAIN, "dismiss_alert", {"uuid": UUID}, blocking=True
    )
    await hass.async_block_till_done()

    dismiss = [c for c in mock_client.call.call_args_list if c.args[0] == "alert.dismiss"]
    assert dismiss[0].args == ("alert.dismiss", UUID)


async def test_restore_alert_calls_client(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """restore_alert calls alert.restore with the uuid."""
    mock_client.call.reset_mock()
    await hass.services.async_call(
        DOMAIN, "restore_alert", {"uuid": UUID}, blocking=True
    )
    await hass.async_block_till_done()

    restore = [c for c in mock_client.call.call_args_list if c.args[0] == "alert.restore"]
    assert restore[0].args == ("alert.restore", UUID)


async def test_dismiss_alert_unknown_entry_raises(
    hass: HomeAssistant, init_integration
) -> None:
    """A bad entry_id raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "dismiss_alert",
            {"uuid": UUID, "entry_id": "does-not-exist"},
            blocking=True,
        )


async def test_services_removed_on_unload(
    hass: HomeAssistant, init_integration
) -> None:
    """Unloading the last entry removes the services."""
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, "dismiss_alert")
    assert not hass.services.has_service(DOMAIN, "restore_alert")
