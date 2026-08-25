"""Config flow for Tapo DL100."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DlklapApi, DlklapAuthError, DlklapError
from .const import (
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_USERNAME,
    CONF_IP,
    CONF_POLL_SECONDS,
    DEFAULT_POLL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class TapoDl100ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tapo DL100."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"tapo_dl100::{user_input[CONF_NAME]}")
            self._abort_if_unique_id_configured()

            try:
                session = async_get_clientsession(self.hass)
                api = DlklapApi(
                    ip=user_input[CONF_IP],
                    cloud_username=user_input[CONF_CLOUD_USERNAME],
                    cloud_password=user_input[CONF_CLOUD_PASSWORD],
                    lock_name=user_input[CONF_NAME],
                    websession=session,
                    logger=_LOGGER,
                )
                await api.get_device_info()
            except DlklapAuthError:
                errors["base"] = "invalid_auth"
            except DlklapError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_IP): str,
                vol.Required(CONF_CLOUD_USERNAME): str,
                vol.Required(CONF_CLOUD_PASSWORD): str,
                vol.Optional(CONF_POLL_SECONDS, default=DEFAULT_POLL_SECONDS): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=3600)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
