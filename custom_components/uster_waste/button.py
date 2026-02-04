"""Button platform for Uster Waste."""
import logging
from typing import Optional

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUAL_REFRESH

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button."""
    config = entry.data
    name = config.get("name", "Uster Waste")

    entity = UsterWasteButton(
        entry_id=entry.entry_id,
        name=name
    )
    async_add_entities([entity])


class UsterWasteButton(ButtonEntity):
    """Uster Waste Button Entity for manual refresh."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        entry_id: str,
        name: str
    ):
        self._entry_id = entry_id
        self._attr_name = MANUAL_REFRESH
        self._attr_unique_id = f"uster_waste_{entry_id}_refresh"

    async def async_press(self) -> None:
        """Handle the button press (manual refresh)."""
        # Trigger a manual update of the sensor
        hass = self.hass
        coordinator = None
        
        # Find the coordinator for this entry
        if DOMAIN in hass.data:
            for entry_id, entry_data in hass.data[DOMAIN].items():
                if entry_id == self._entry_id and "coordinator" in entry_data:
                    coordinator = entry_data["coordinator"]
                    break
        
        if coordinator:
            await coordinator.async_update()
            # Force sensor to update
            for entity in coordinator.entities:
                await entity.async_update()
                entity.async_write_ha_state()
        else:
            _LOGGER.error("Coordinator not found for manual refresh")