"""Tests for truenas_ng config-entry diagnostics redaction and content."""
from __future__ import annotations

import pytest
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from custom_components.truenas_ng.diagnostics import (
    async_get_config_entry_diagnostics,
)

DATA_POOL_GUID = "1111111111111111111"
# F8: disks are now keyed by devname, not serial
WD_DISK_DEVNAME = "sda"
WD_DISK_SERIAL = "WD-DEADBEEF01"


async def test_diagnostics_redacts_api_key(
    hass: HomeAssistant, init_integration
) -> None:
    """The API key is redacted; non-secret connection fields are preserved."""
    diag = await async_get_config_entry_diagnostics(hass, init_integration)

    assert diag["entry"]["data"][CONF_API_KEY] == REDACTED
    assert diag["entry"]["data"][CONF_HOST] == "truenas.local"
    assert diag["entry"]["data"][CONF_PORT] == 9443


async def test_diagnostics_includes_pool_and_redacts_serial(
    hass: HomeAssistant, init_integration
) -> None:
    """Pool data is present; disk serials are redacted; system/reporting snapshots exist."""
    diag = await async_get_config_entry_diagnostics(hass, init_integration)

    assert DATA_POOL_GUID in diag["storage"]["pools"]
    assert diag["storage"]["pools"][DATA_POOL_GUID]["name"] == "Data"

    # F8: disks are re-keyed by devname so raw serials don't appear as keys;
    # the inner "serial" value field is still redacted by async_redact_data.
    assert WD_DISK_DEVNAME in diag["storage"]["disks"]
    assert diag["storage"]["disks"][WD_DISK_DEVNAME]["serial"] == REDACTED
    # Confirm the raw serial string no longer appears as a key
    assert WD_DISK_SERIAL not in diag["storage"]["disks"]

    assert diag["system"]["info"]["hostname"] == "truenas"
    assert diag["reporting"]["memory_free"] == 30234440000
    assert "Data" in diag["datasets"]
