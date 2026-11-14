"""Tests for dropping the devices of TrueNAS apps and VMs that are gone."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.truenas_ng import async_remove_config_entry_device
from custom_components.truenas_ng.client import TrueNASError
from custom_components.truenas_ng.const import CONF_ENABLE_VMS, DOMAIN

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _entry(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    """Add a config entry to hass without setting it up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST_ID,
        data={
            CONF_HOST: "truenas.local",
            CONF_PORT: 9443,
            CONF_USERNAME: "homeassistant",
            CONF_API_KEY: "1-test",
            CONF_VERIFY_SSL: True,
        },
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


async def _setup(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Set the entry up with the mocked client."""
    with patch(
        "custom_components.truenas_ng.TrueNASClient", return_value=mock_client
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _leftover(
    hass: HomeAssistant, entry: MockConfigEntry, kind: str, key: str
) -> tuple[str, str]:
    """Register a child device and one entity on it, as an earlier run left them."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{HOST_ID}_{kind}_{key}")},
        name=f"{kind} {key}",
    )
    entity = er.async_get(hass).async_get_or_create(
        "switch",
        DOMAIN,
        f"{HOST_ID}_{kind}_{key}_switch",
        config_entry=entry,
        device_id=device.id,
    )
    return device.id, entity.entity_id


def _fail(mock_client: MagicMock, method: str) -> None:
    """Make one RPC method raise, as when its subsystem is down."""
    answer = mock_client.call.side_effect

    def _call(name: str, *params: object, **kwargs: object) -> object:
        if name == method:
            raise TrueNASError(f"{method} failed")
        return answer(name, *params, **kwargs)

    mock_client.call.side_effect = _call


async def _refresh(hass: HomeAssistant, coordinator) -> None:
    """Run one poll of a coordinator and let its listeners finish."""
    await coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_removed_app_device_goes_after_two_listings(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """An app TrueNAS stopped listing loses its device and entities at the 2nd listing."""
    entry = _entry(hass)
    device_id, entity_id = _leftover(hass, entry, "app", "old-app")
    await _setup(hass, entry, mock_client)
    devices = dr.async_get(hass)

    # Setup's listing is the first without it, so the device stays for now.
    assert devices.async_get(device_id) is not None

    await _refresh(hass, entry.runtime_data.apps)

    assert devices.async_get(device_id) is None
    assert er.async_get(hass).async_get(entity_id) is None
    # The listed apps and the hub keep their devices.
    for name in ("radarr", "jellyfin", "sabnzbd"):
        assert devices.async_get_device_by_identifier(
            (DOMAIN, f"{HOST_ID}_app_{name}"), entry.entry_id
        )
    assert devices.async_get_device_by_identifier((DOMAIN, HOST_ID), entry.entry_id)


async def test_removed_vm_device_goes_after_two_listings(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """A VM TrueNAS stopped listing loses its device; the listed VMs keep theirs."""
    entry = _entry(hass)
    device_id, entity_id = _leftover(hass, entry, "vm", "9")
    await _setup(hass, entry, mock_client)
    devices = dr.async_get(hass)
    assert devices.async_get(device_id) is not None

    await _refresh(hass, entry.runtime_data.vms)

    assert devices.async_get(device_id) is None
    assert er.async_get(hass).async_get(entity_id) is None
    for vm_id in (1, 2):
        assert devices.async_get_device_by_identifier(
            (DOMAIN, f"{HOST_ID}_vm_{vm_id}"), entry.entry_id
        )


async def test_unanswered_listing_does_not_count(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """While app.query fails nothing goes; the next answered listing counts as 2nd."""
    entry = _entry(hass)
    device_id, _ = _leftover(hass, entry, "app", "old-app")
    await _setup(hass, entry, mock_client)
    answer = mock_client.call.side_effect
    devices = dr.async_get(hass)

    _fail(mock_client, "app.query")
    for _ in range(3):
        await _refresh(hass, entry.runtime_data.apps)
    assert devices.async_get(device_id) is not None
    # The listed apps' devices stay too, though the failed listing came back empty.
    assert devices.async_get_device_by_identifier(
        (DOMAIN, f"{HOST_ID}_app_radarr"), entry.entry_id
    )

    mock_client.call.side_effect = answer
    await _refresh(hass, entry.runtime_data.apps)
    assert devices.async_get(device_id) is None


async def test_empty_listing_does_not_count(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """An empty app listing removes nothing, however many times it comes back."""
    mock_client._dispatch["app.query"] = []
    entry = _entry(hass)
    device_id, _ = _leftover(hass, entry, "app", "old-app")
    await _setup(hass, entry, mock_client)

    for _ in range(3):
        await _refresh(hass, entry.runtime_data.apps)

    assert dr.async_get(hass).async_get(device_id) is not None


async def test_device_back_in_listing_starts_over(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """A device listed again needs two more listings without it before it goes."""
    listing = mock_client._dispatch["app.query"]
    entry = _entry(hass)
    device_id, _ = _leftover(hass, entry, "app", "old-app")
    await _setup(hass, entry, mock_client)  # left out once
    devices = dr.async_get(hass)

    mock_client._dispatch["app.query"] = [*listing, {"name": "old-app", "state": "RUNNING"}]
    await _refresh(hass, entry.runtime_data.apps)  # listed again
    mock_client._dispatch["app.query"] = listing
    await _refresh(hass, entry.runtime_data.apps)  # left out once more
    assert devices.async_get(device_id) is not None

    await _refresh(hass, entry.runtime_data.apps)  # twice in a row
    assert devices.async_get(device_id) is None


async def test_no_cleanup_while_vm_entities_are_off(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """With the VM group turned off in options, nothing watches the VM listing."""
    entry = _entry(hass, {CONF_ENABLE_VMS: False})
    device_id, _ = _leftover(hass, entry, "vm", "9")
    await _setup(hass, entry, mock_client)

    for _ in range(2):
        await _refresh(hass, entry.runtime_data.vms)

    assert dr.async_get(hass).async_get(device_id) is not None


async def test_user_may_delete_only_unreported_devices(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """The device page's delete works on unreported children, never the hub."""
    entry = _entry(hass)
    stale = {
        kind: _leftover(hass, entry, kind, key)[0]
        for kind, key in (
            ("app", "old-app"),
            ("vm", "9"),
            ("pool", "999"),
            ("disk", "GONE_SERIAL"),
        )
    }
    old_host = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "fedcba9876543210_app_radarr")},
        name="App radarr (old host id)",
    )
    await _setup(hass, entry, mock_client)
    devices = dr.async_get(hass)
    storage = entry.runtime_data.storage.data

    async def removable(identifier: str) -> bool:
        device = devices.async_get_device_by_identifier(
            (DOMAIN, identifier), entry.entry_id
        )
        assert device is not None, identifier
        return await async_remove_config_entry_device(hass, entry, device)

    assert not await removable(HOST_ID)
    assert not await removable(f"{HOST_ID}_app_radarr")
    assert not await removable(f"{HOST_ID}_vm_1")
    assert not await removable(f"{HOST_ID}_pool_{next(iter(storage.pools))}")
    assert not await removable(f"{HOST_ID}_disk_{next(iter(storage.disks))}")
    for device_id in stale.values():
        assert await async_remove_config_entry_device(
            hass, entry, devices.async_get(device_id)
        )
    assert await async_remove_config_entry_device(hass, entry, old_host)


async def test_delete_refused_while_app_listing_unanswered(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """With app.query failing, no app device counts as gone, so none may be deleted."""
    entry = _entry(hass)
    device_id, _ = _leftover(hass, entry, "app", "old-app")
    await _setup(hass, entry, mock_client)
    _fail(mock_client, "app.query")
    await _refresh(hass, entry.runtime_data.apps)

    device = dr.async_get(hass).async_get(device_id)
    assert not await async_remove_config_entry_device(hass, entry, device)


async def test_delete_refused_while_entry_unloaded(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """An unloaded entry can't tell what TrueNAS reports, so it refuses deletes."""
    entry = _entry(hass)
    device_id, _ = _leftover(hass, entry, "app", "old-app")
    await _setup(hass, entry, mock_client)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    device = dr.async_get(hass).async_get(device_id)
    assert not await async_remove_config_entry_device(hass, entry, device)


async def test_device_page_delete(
    hass: HomeAssistant, mock_client: MagicMock, hass_ws_client: WebSocketGenerator
) -> None:
    """Deleting through the device registry API: allowed for a stale disk, not the hub."""
    assert await async_setup_component(hass, "config", {})
    entry = _entry(hass)
    device_id, entity_id = _leftover(hass, entry, "disk", "GONE_SERIAL")
    await _setup(hass, entry, mock_client)
    devices = dr.async_get(hass)
    hub = devices.async_get_device_by_identifier((DOMAIN, HOST_ID), entry.entry_id)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "config/device_registry/remove", "device_id": hub.id}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert devices.async_get(hub.id) is not None

    await client.send_json_auto_id(
        {"type": "config/device_registry/remove", "device_id": device_id}
    )
    response = await client.receive_json()
    assert response["success"]
    assert devices.async_get(device_id) is None
    assert er.async_get(hass).async_get(entity_id) is None
