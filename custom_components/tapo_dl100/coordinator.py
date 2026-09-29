"""Coordinator for Tapo DL100 state."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DeviceInfo, DlklapApi
from .const import (
    DOMAIN,
    EVENT_LOCK_CHANGED,
    SOURCE_EXTERNAL,
    SOURCE_HOME_ASSISTANT,
)

PENDING_COMMAND_WINDOW = timedelta(seconds=60)
LOCK_STATUS_NAMES = {0: "locked", 1: "unlocked"}


class Dl100Coordinator(DataUpdateCoordinator[DeviceInfo]):
    """Coordinate DL100 updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DlklapApi,
        update_interval_seconds: int,
        entry_id: str,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=api.log,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.api = api
        self.entry_id = entry_id
        self.lock_entity_id: str | None = None
        self.last_changed_by: str | None = None
        self.last_changed_at: datetime | None = None
        self._previous: DeviceInfo | None = None
        self._pending_status: int | None = None
        self._pending_at: datetime | None = None

    def mark_pending_command(self, locked: bool) -> None:
        """Remember a lock/unlock issued by Home Assistant for source attribution."""
        self._pending_status = 0 if locked else 1
        self._pending_at = dt_util.utcnow()

    def _take_pending_match(self, status: int) -> bool:
        if self._pending_status is None or self._pending_at is None:
            return False
        matched = (
            self._pending_status == status
            and dt_util.utcnow() - self._pending_at <= PENDING_COMMAND_WINDOW
        )
        self._pending_status = None
        self._pending_at = None
        return matched

    async def _async_update_data(self) -> DeviceInfo:
        try:
            info = await self.api.get_device_info()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(str(err)) from err

        previous = self._previous
        self._previous = info
        if previous is not None:
            self._log_raw_diff(previous.raw, info.raw)
            if previous.lock_status != info.lock_status:
                self._handle_lock_change(previous.lock_status, info)
        return info

    def _handle_lock_change(self, old_status: int, info: DeviceInfo) -> None:
        source = (
            SOURCE_HOME_ASSISTANT
            if self._take_pending_match(info.lock_status)
            else SOURCE_EXTERNAL
        )
        self.last_changed_by = source
        self.last_changed_at = dt_util.utcnow()
        self.hass.bus.async_fire(
            EVENT_LOCK_CHANGED,
            {
                "entry_id": self.entry_id,
                "entity_id": self.lock_entity_id,
                "old": LOCK_STATUS_NAMES.get(old_status, str(old_status)),
                "new": LOCK_STATUS_NAMES.get(info.lock_status, str(info.lock_status)),
                "source": source,
                "battery_percentage": info.battery_percentage,
            },
        )

    def _log_raw_diff(self, old: dict, new: dict) -> None:
        changed = {
            key: (old.get(key), new.get(key))
            for key in old.keys() | new.keys()
            if old.get(key) != new.get(key)
        }
        if changed:
            self.logger.debug("getDeviceInfo fields changed: %s", changed)
