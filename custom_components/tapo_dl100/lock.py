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
        if "rssi" in info.raw:
            attrs["rssi"] = info.raw["rssi"]
        return attrs

    async def async_lock(self, **kwargs) -> None:
        try:
            await self.coordinator.api.set_lock(True)
        finally:
            await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs) -> None:
        try:
            await self.coordinator.api.set_lock(False)
        finally:
            await self.coordinator.async_request_refresh()
