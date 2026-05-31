"""Tests for the truenas_ng button platform."""
from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.truenas_ng.const import DOMAIN

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    """Invoke the button.press service for a single entity and wait for it."""
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_button_entities_created(hass: HomeAssistant, init_integration) -> None:
    """Per-pool scrub buttons plus system reboot/shutdown exist with C4 unique_ids."""
    registry = er.async_get(hass)

    # Two pools in the fixture -> two scrub buttons, plus reboot + shutdown.
    button_entries = [
        entry
        for entry in registry.entities.values()
        if entry.domain == "button" and entry.platform == DOMAIN
    ]
    assert len(button_entries) == 4

    unique_ids = {entry.unique_id for entry in button_entries}
    assert f"{HOST_ID}_pool_1111111111111111111_scrub" in unique_ids
    assert f"{HOST_ID}_pool_2222222222222222222_scrub" in unique_ids
    assert f"{HOST_ID}_system_reboot" in unique_ids
    assert f"{HOST_ID}_system_shutdown" in unique_ids

    # All buttons are config-category entities.
    for entry in button_entries:
        assert entry.entity_category is EntityCategory.CONFIG


async def test_scrub_button_press_calls_pool_scrub(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """Pressing the Data pool scrub button calls pool.scrub with id 1 and job=True."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{HOST_ID}_pool_1111111111111111111_scrub"
    )
    assert entity_id is not None

    mock_client.call.reset_mock()
    await _press(hass, entity_id)

    mock_client.call.assert_called_once()
    args, kwargs = mock_client.call.call_args
    assert args == ("pool.scrub", 1, "START")
    assert kwargs == {"job": True}


async def test_reboot_button_press_calls_system_reboot(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """Pressing the reboot button calls system.reboot with a non-empty reason and job=True."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{HOST_ID}_system_reboot"
    )
    assert entity_id is not None

    mock_client.call.reset_mock()
    await _press(hass, entity_id)

    mock_client.call.assert_called_once()
    args, kwargs = mock_client.call.call_args
    assert args == ("system.reboot", "Initiated from Home Assistant")
    assert kwargs == {"job": True}


async def test_shutdown_button_press_calls_system_shutdown(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """Pressing the shutdown button calls system.shutdown with a non-empty reason and job=True."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{HOST_ID}_system_shutdown"
    )
    assert entity_id is not None

    mock_client.call.reset_mock()
    await _press(hass, entity_id)

    mock_client.call.assert_called_once()
    args, kwargs = mock_client.call.call_args
    assert args == ("system.shutdown", "Initiated from Home Assistant")
    assert kwargs == {"job": True}
