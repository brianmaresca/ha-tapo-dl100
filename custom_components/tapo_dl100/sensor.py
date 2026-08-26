"""Sensor platform for Tapo DL100."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE, EntityCategory
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
    """Set up DL100 battery sensor entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: Dl100Coordinator = data["coordinator"]
    async_add_entities([Dl100BatterySensor(entry, coordinator)])


class Dl100BatterySensor(CoordinatorEntity[Dl100Coordinator], SensorEntity):
    """Battery level sensor for a Tapo DL100 lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_icon = "mdi:battery"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, coordinator: Dl100Coordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_battery"
        self._attr_name = f"{entry.data[CONF_NAME]} Battery"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> int | None:
        info: DeviceInfo | None = self.coordinator.data
        if info is None:
            return None
        return info.battery_percentage

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        info: DeviceInfo | None = self.coordinator.data
        if info is None:
            return {}
        return {"at_low_battery": info.at_low_battery}
