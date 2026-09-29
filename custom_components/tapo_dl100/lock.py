"""Lock platform for Tapo DL100."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import DeviceInfo
from .const import DOMAIN
from .coordinator import Dl100Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DL100 lock entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: Dl100Coordinator = data["coordinator"]
    async_add_entities([Dl100LockEntity(entry, coordinator)])


class Dl100LockEntity(CoordinatorEntity[Dl100Coordinator], LockEntity):
    """Representation of a Tapo DL100 lock."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator: Dl100Coordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_lock"
        self._attr_name = entry.data[CONF_NAME]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.lock_entity_id = self.entity_id

    @property
    def changed_by(self) -> str | None:
        return self.coordinator.last_changed_by

    @property
    def is_locked(self) -> bool | None:
        info = self.coordinator.data
        if info is None:
            return None
        if info.lock_status == 0:
            return True
        if info.lock_status == 1:
            return False
        return None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        info: DeviceInfo | None = self.coordinator.data
        if info is None:
            return {}
        attrs: dict[str, object] = {
            "lock_status": info.lock_status,
            "at_low_battery": info.at_low_battery,
            "battery_percentage": info.battery_percentage,
        }
        attrs["connectivity"] = (
            "online" if self.coordinator.last_update_success else "offline"
        )
        if self.coordinator.api.last_connect_error:
            attrs["last_connect_error"] = self.coordinator.api.last_connect_error
        if self.coordinator.api.last_success_at:
            attrs["last_success_at"] = self.coordinator.api.last_success_at
        if self.coordinator.last_changed_at:
            attrs["last_changed_at"] = self.coordinator.last_changed_at.isoformat()
        if "rssi" in info.raw:
            attrs["rssi"] = info.raw["rssi"]
        if "wifi_mode_status" in info.raw:
            attrs["wifi_mode_status"] = info.raw["wifi_mode_status"]
        return attrs

    async def async_lock(self, **kwargs) -> None:
        self.coordinator.mark_pending_command(True)
        try:
            await self.coordinator.api.set_lock(True)
        finally:
            await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs) -> None:
        self.coordinator.mark_pending_command(False)
        try:
            await self.coordinator.api.set_lock(False)
        finally:
            await self.coordinator.async_request_refresh()
