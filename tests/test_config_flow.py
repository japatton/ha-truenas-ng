"""Tests for the truenas_ng config flow."""

from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.truenas_ng.client import (
    TrueNASAuthError,
    TrueNASConnectionError,
)
from custom_components.truenas_ng.const import DOMAIN

_FIXTURES = pathlib.Path(__file__).parent / "fixtures"

HOST_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

USER_INPUT = {
    CONF_HOST: "truenas.local",
    CONF_PORT: 9443,
    CONF_USERNAME: "homeassistant",
    CONF_API_KEY: "1-test",
    CONF_VERIFY_SSL: True,
}


def _flow_client() -> MagicMock:
    """Build a MagicMock standing in for TrueNASClient inside the flow.

    .connect() is a no-op; .call() dispatches the two methods the user step
    needs (system.info, system.host_id) to the recon fixtures.
    """
    client = MagicMock()
    info = json.loads((_FIXTURES / "system_info.json").read_text())

    def _call(method: str, *args, **kwargs):
        if method == "system.info":
            return info
        if method == "system.host_id":
            return HOST_ID
        raise AssertionError(f"unexpected method {method}")

    client.call.side_effect = _call
    return client


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A full user flow creates the entry with unique_id host_id and title host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    client = _flow_client()
    with (
        patch(
            "custom_components.truenas_ng.config_flow.TrueNASClient",
            return_value=client,
        ),
        patch(
            "custom_components.truenas_ng.async_setup_entry",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "truenas.local"
    assert result["result"].unique_id == HOST_ID
    assert result["data"] == USER_INPUT
    # The flow validated by constructing the client and probing both methods.
    client.connect.assert_called_once()
    assert client.call.call_count == 2
    assert len(mock_setup.mock_calls) >= 1


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """connect() raising TrueNASConnectionError re-shows the form with cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    client = MagicMock()
    client.connect.side_effect = TrueNASConnectionError("no route to host")
    with patch(
        "custom_components.truenas_ng.config_flow.TrueNASClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """connect() raising TrueNASAuthError re-shows the form with invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    client = MagicMock()
    client.connect.side_effect = TrueNASAuthError("bad api key")
    with patch(
        "custom_components.truenas_ng.config_flow.TrueNASClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_duplicate_aborts(hass: HomeAssistant) -> None:
    """A second entry with the same host_id aborts already_configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST_ID,
        data=USER_INPUT,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    client = _flow_client()
    with patch(
        "custom_components.truenas_ng.config_flow.TrueNASClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_updates_key(hass: HomeAssistant) -> None:
    """Reauth confirm rotates the API key and reloads the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST_ID,
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    client = _flow_client()
    with (
        patch(
            "custom_components.truenas_ng.config_flow.TrueNASClient",
            return_value=client,
        ),
        patch(
            "custom_components.truenas_ng.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "2-rotated"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "2-rotated"
    # Unchanged keys are preserved.
    assert entry.data[CONF_HOST] == "truenas.local"


async def test_reconfigure_flow_updates_host(hass: HomeAssistant) -> None:
    """Reconfigure updates host/port/SSL when host_id still matches."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST_ID,
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {**USER_INPUT, CONF_HOST: "nas2.local", CONF_VERIFY_SSL: False}
    client = _flow_client()
    with (
        patch(
            "custom_components.truenas_ng.config_flow.TrueNASClient",
            return_value=client,
        ),
        patch(
            "custom_components.truenas_ng.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "nas2.local"
    assert entry.data[CONF_VERIFY_SSL] is False
    # unique_id is unchanged because host_id is stable.
    assert entry.unique_id == HOST_ID


async def test_options_flow_sets_intervals_and_toggles(
    hass: HomeAssistant, init_integration
) -> None:
    """The options flow stores intervals and group toggles on the entry."""
    from custom_components.truenas_ng.const import (
        CONF_ENABLE_DATASETS,
        CONF_INTERVAL_STORAGE,
    )

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INTERVAL_STORAGE: 45,
                "interval_datasets": 600,
                "interval_system": 90,
                "interval_reporting": 30,
                "interval_update": 43200,
                CONF_ENABLE_DATASETS: True,
                "enable_disks": True,
                "enable_reporting": False,
                "enable_service_controls": True,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options[CONF_INTERVAL_STORAGE] == 45
    assert init_integration.options[CONF_ENABLE_DATASETS] is True
    assert init_integration.options["enable_reporting"] is False
