"""Coordinator for Tapo DL100 state."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DeviceInfo, DlklapApi
from .const import DOMAIN


class Dl100Coordinator(DataUpdateCoordinator[DeviceInfo]):
    """Coordinate DL100 updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DlklapApi,
        update_interval_seconds: int,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=api.log,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.api = api

    async def _async_update_data(self) -> DeviceInfo:
        try:
            return await self.api.get_device_info()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(str(err)) from err
