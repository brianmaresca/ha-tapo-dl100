"""The Tapo DL100 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DlklapApi
from .const import (
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_USERNAME,
    CONF_IP,
    CONF_POLL_SECONDS,
    DEFAULT_POLL_SECONDS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import Dl100Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tapo DL100 from a config entry."""
    cfg = {**entry.data, **entry.options}
    session = async_get_clientsession(hass)
    api = DlklapApi(
        ip=cfg[CONF_IP],
        cloud_username=cfg[CONF_CLOUD_USERNAME],
        cloud_password=cfg[CONF_CLOUD_PASSWORD],
        lock_name=cfg[CONF_NAME],
        websession=session,
        logger=_LOGGER,
        terminal_uuid=entry.data.get("terminal_uuid"),
        device_id=entry.data.get("device_id"),
    )
    coordinator = Dl100Coordinator(
        hass=hass,
        api=api,
        update_interval_seconds=entry.options.get(
            CONF_POLL_SECONDS, entry.data.get(CONF_POLL_SECONDS, DEFAULT_POLL_SECONDS)
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    if (
        api.terminal_uuid
        and api.device_id
        and (
            entry.data.get("terminal_uuid") != api.terminal_uuid
            or entry.data.get("device_id") != api.device_id
        )
    ):
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "terminal_uuid": api.terminal_uuid,
                "device_id": api.device_id,
            },
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
