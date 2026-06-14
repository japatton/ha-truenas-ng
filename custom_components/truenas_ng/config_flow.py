"""Config flow for the TrueNAS (Native) integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback

from .client import (
    TrueNASAuthError,
    TrueNASClient,
    TrueNASConnectionError,
    TrueNASError,
)
from .const import (
    CONF_ENABLE_APPS,
    CONF_ENABLE_DATASETS,
    CONF_ENABLE_DISKS,
    CONF_ENABLE_REPORTING,
    CONF_ENABLE_SERVICE_CONTROLS,
    CONF_ENABLE_VMS,
    CONF_INTERVAL_APPS,
    CONF_INTERVAL_DATASETS,
    CONF_INTERVAL_REPORTING,
    CONF_INTERVAL_STORAGE,
    CONF_INTERVAL_SYSTEM,
    CONF_INTERVAL_UPDATE,
    CONF_INTERVAL_VMS,
    DEFAULT_ENABLE_APPS,
    DEFAULT_ENABLE_DATASETS,
    DEFAULT_ENABLE_DISKS,
    DEFAULT_ENABLE_REPORTING,
    DEFAULT_ENABLE_SERVICE_CONTROLS,
    DEFAULT_ENABLE_VMS,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SCAN_INTERVAL_APPS,
    SCAN_INTERVAL_DATASETS,
    SCAN_INTERVAL_REPORTING,
    SCAN_INTERVAL_STORAGE,
    SCAN_INTERVAL_SYSTEM,
    SCAN_INTERVAL_UPDATE,
    SCAN_INTERVAL_VMS,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the form schema, pre-filling from defaults (for reconfigure)."""
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)
            ): str,
            vol.Required(
                CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
            ): int,
            vol.Required(
                CONF_USERNAME,
                default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME),
            ): str,
            vol.Required(CONF_API_KEY): str,
            vol.Required(
                CONF_VERIFY_SSL,
                default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): bool,
        }
    )


def _validate(hass: HomeAssistant, data: Mapping[str, Any]) -> str:
    """Connect with the supplied credentials and return the host_id.

    Runs the synchronous TrueNASClient on a worker thread. Raises
    TrueNASAuthError / TrueNASConnectionError / TrueNASError on failure.
    """
    client = TrueNASClient(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        api_key=data[CONF_API_KEY],
        verify_ssl=data[CONF_VERIFY_SSL],
    )
    try:
        client.connect()
        client.call("system.info")
        host_id = client.call("system.host_id")
    finally:
        client.close()
    return str(host_id)


class TrueNASConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TrueNAS (Native)."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "TrueNASOptionsFlow":
        """Return the options flow handler."""
        return TrueNASOptionsFlow()

    async def _async_probe(
        self, data: Mapping[str, Any], errors: dict[str, str]
    ) -> str | None:
        """Validate credentials on the executor; fill errors and return host_id."""
        try:
            host_id = await self.hass.async_add_executor_job(
                _validate, self.hass, dict(data)
            )
        except TrueNASAuthError:
            errors["base"] = "invalid_auth"
        except TrueNASConnectionError:
            errors["base"] = "cannot_connect"
        except TrueNASError:
            errors["base"] = "unknown"
        except Exception:  # noqa: BLE001 - surface unexpected failures as 'unknown'
            _LOGGER.exception("Unexpected error validating TrueNAS connection")
            errors["base"] = "unknown"
        else:
            return host_id
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host_id = await self._async_probe(user_input, errors)
            if host_id is not None:
                await self.async_set_unique_id(host_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauth triggered by ConfigEntryAuthFailed."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth: rotate the API key, keeping the same host_id."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**reauth_entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
            host_id = await self._async_probe(data, errors)
            if host_id is not None:
                await self.async_set_unique_id(host_id)
                self._abort_if_unique_id_mismatch(reason="wrong_host")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of host / port / SSL, keeping the same host_id."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            host_id = await self._async_probe(user_input, errors)
            if host_id is not None:
                await self.async_set_unique_id(host_id)
                self._abort_if_unique_id_mismatch(reason="wrong_host")
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or reconfigure_entry.data),
            errors=errors,
        )


def _interval(value: int) -> int:
    """Validate a poll interval (seconds)."""
    return vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL))(value)


class TrueNASOptionsFlow(OptionsFlow):
    """Tune poll intervals and which entity groups are created."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show/process the single options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_INTERVAL_STORAGE,
                    default=opts.get(CONF_INTERVAL_STORAGE, SCAN_INTERVAL_STORAGE),
                ): _interval,
                vol.Required(
                    CONF_INTERVAL_DATASETS,
                    default=opts.get(CONF_INTERVAL_DATASETS, SCAN_INTERVAL_DATASETS),
                ): _interval,
                vol.Required(
                    CONF_INTERVAL_SYSTEM,
                    default=opts.get(CONF_INTERVAL_SYSTEM, SCAN_INTERVAL_SYSTEM),
                ): _interval,
                vol.Required(
                    CONF_INTERVAL_REPORTING,
                    default=opts.get(CONF_INTERVAL_REPORTING, SCAN_INTERVAL_REPORTING),
                ): _interval,
                vol.Required(
                    CONF_INTERVAL_UPDATE,
                    default=opts.get(CONF_INTERVAL_UPDATE, SCAN_INTERVAL_UPDATE),
                ): _interval,
                vol.Required(
                    CONF_INTERVAL_APPS,
                    default=opts.get(CONF_INTERVAL_APPS, SCAN_INTERVAL_APPS),
                ): _interval,
                vol.Required(
                    CONF_INTERVAL_VMS,
                    default=opts.get(CONF_INTERVAL_VMS, SCAN_INTERVAL_VMS),
                ): _interval,
                vol.Required(
                    CONF_ENABLE_DATASETS,
                    default=opts.get(CONF_ENABLE_DATASETS, DEFAULT_ENABLE_DATASETS),
                ): bool,
                vol.Required(
                    CONF_ENABLE_DISKS,
                    default=opts.get(CONF_ENABLE_DISKS, DEFAULT_ENABLE_DISKS),
                ): bool,
                vol.Required(
                    CONF_ENABLE_REPORTING,
                    default=opts.get(CONF_ENABLE_REPORTING, DEFAULT_ENABLE_REPORTING),
                ): bool,
                vol.Required(
                    CONF_ENABLE_SERVICE_CONTROLS,
                    default=opts.get(
                        CONF_ENABLE_SERVICE_CONTROLS, DEFAULT_ENABLE_SERVICE_CONTROLS
                    ),
                ): bool,
                vol.Required(
                    CONF_ENABLE_APPS,
                    default=opts.get(CONF_ENABLE_APPS, DEFAULT_ENABLE_APPS),
                ): bool,
                vol.Required(
                    CONF_ENABLE_VMS,
                    default=opts.get(CONF_ENABLE_VMS, DEFAULT_ENABLE_VMS),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
