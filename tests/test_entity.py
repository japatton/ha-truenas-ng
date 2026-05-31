"""Tests for custom_components.truenas_ng.entity device_info helpers."""
from __future__ import annotations

from pytest_homeassistant_custom_component.common import (
    load_json_array_fixture,
    load_json_object_fixture,
)

from custom_components.truenas_ng.const import DOMAIN, MANUFACTURER
from custom_components.truenas_ng.entity import (
    disk_device_info,
    hub_device_info,
    pool_device_info,
)

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def test_hub_device_info() -> None:
    """hub_device_info derives identifiers/name/model/sw_version from system.info."""
    info = load_json_object_fixture("system_info.json")

    device = hub_device_info(HOST_ID, info)

    assert device["identifiers"] == {(DOMAIN, HOST_ID)}
    assert device["name"] == "TrueNAS truenas"
    assert device["manufacturer"] == MANUFACTURER
    assert device["model"] == "WTR MAX"
    assert device["sw_version"] == "26.0.0-BETA.1"


def test_pool_device_info() -> None:
    """pool_device_info uses the pool guid and links back to the hub via_device."""
    pools = load_json_array_fixture("pool_query.json")
    pool = pools[0]
    assert pool["guid"] == "1111111111111111111"

    device = pool_device_info(HOST_ID, pool)

    assert device["identifiers"] == {
        (DOMAIN, f"{HOST_ID}_pool_1111111111111111111")
    }
    assert device["name"] == "Pool Data"
    assert device["manufacturer"] == MANUFACTURER
    assert device["model"] == "ZFS Pool"
    assert device["via_device"] == (DOMAIN, HOST_ID)


def test_disk_device_info() -> None:
    """disk_device_info names the disk and links it to the hub via_device."""
    disks = load_json_array_fixture("disk_query.json")
    disk = next(d for d in disks if d["name"] == "sda")
    assert disk["serial"] == "WD-DEADBEEF01"

    device = disk_device_info(HOST_ID, disk)

    assert device["identifiers"] == {(DOMAIN, f"{HOST_ID}_disk_WD-DEADBEEF01")}
    assert device["name"] == "Disk sda"
    assert device["manufacturer"] == MANUFACTURER
    assert device["model"] == "WDC WD20EFZX-68AWUN0"
    assert device["via_device"] == (DOMAIN, HOST_ID)


def test_hub_device_info_falls_back_when_fields_missing() -> None:
    """Missing system_product falls back to 'TrueNAS'; blank hostname is stripped."""
    device = hub_device_info(HOST_ID, {})

    assert device["identifiers"] == {(DOMAIN, HOST_ID)}
    assert device["name"] == "TrueNAS"
    assert device["model"] == "TrueNAS"
    assert device.get("sw_version") is None
