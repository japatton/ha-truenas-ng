"""Shared pytest fixtures for the truenas_ng test suite (Shared Contract C6)."""

from __future__ import annotations

import json
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    load_fixture,
    load_json_array_fixture,
    load_json_object_fixture,
)

from custom_components.truenas_ng.const import DOMAIN

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading of the truenas_ng custom integration in every test."""
    yield


def _build_dispatch() -> dict[str, object]:
    """Map RPC method name -> the fixture payload it should return."""
    return {
        "system.info": load_json_object_fixture("system_info.json"),
        "system.host_id": json.loads(load_fixture("host_id.json")),
        "pool.query": load_json_array_fixture("pool_query.json"),
        "disk.query": load_json_array_fixture("disk_query.json"),
        "disk.temperatures": load_json_object_fixture(
            "disk_temperatures.json"
        ),
        "pool.dataset.query": load_json_array_fixture("dataset_query.json"),
        "alert.list": load_json_array_fixture("alert_list.json"),
        "service.query": load_json_array_fixture("service_query.json"),
        "reporting.get_data": load_json_array_fixture(
            "reporting_get_data.json"
        ),
        "pool.scrub": None,
        "system.reboot": None,
        "system.shutdown": None,
        "alert.dismiss": None,
    }


@pytest.fixture
def mock_client() -> MagicMock:
    """A synchronous MagicMock standing in for TrueNASClient.

    `.call` dispatches by method name to the loaded C7 fixtures; unknown
    methods raise AssertionError. `.connect`/`.close` are no-ops; `.ping`
    returns True. This is a plain MagicMock (NOT AsyncMock): the real client
    runs on the executor thread.
    """
    dispatch = _build_dispatch()

    def _call(method: str, *params: object, **kwargs: object) -> object:
        assert method in dispatch, f"unexpected RPC method: {method}"
        return dispatch[method]

    client = MagicMock()
    client.call.side_effect = _call
    client.connect.return_value = None
    client.close.return_value = None
    client.ping.return_value = True
    return client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_client: MagicMock
) -> MockConfigEntry:
    """Set up the integration with the mocked client and return the entry."""
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
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.truenas_ng.TrueNASClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry
