"""Logbook descriptions for Tapo DL100 events."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_LOCK_CHANGED, SOURCE_HOME_ASSISTANT


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe Tapo DL100 logbook events."""

    @callback
    def async_describe_lock_event(event: Event) -> dict[str, str]:
        data = event.data
        new_state = data.get("new", "changed")
        if data.get("source") == SOURCE_HOME_ASSISTANT:
            message = f"was {new_state} by Home Assistant"
        else:
            message = f"was {new_state} externally (keypad, key, auto-lock, or Tapo app)"

        entity_id = data.get("entity_id")
        name = "Tapo lock"
        if entity_id and (state := hass.states.get(entity_id)):
            name = state.name

        entry = {LOGBOOK_ENTRY_NAME: name, LOGBOOK_ENTRY_MESSAGE: message}
        if entity_id:
            entry[LOGBOOK_ENTRY_ENTITY_ID] = entity_id
        return entry

    async_describe_event(DOMAIN, EVENT_LOCK_CHANGED, async_describe_lock_event)
