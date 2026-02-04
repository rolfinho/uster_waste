"""Button platform for Uster Waste."""
import logging

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
    entity = UsterWasteButton(
        entry_id=entry.entry_id,
        name=entry.data.get("name", "Uster Waste")
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
        # Trigger a manual update by calling the sensor's update method
        # The sensor will fetch fresh data from the Uster website
        entity_registry = self.hass.data["entity_registry"]
        
        # Find the sensor entity for this entry
        entity_id = f"sensor.uster_waste_{self._entry_id}"
        
        # Trigger update for the sensor
        await self.hass.services.async_call(
            "homeassistant", "update_entity",
            {"entity_id": entity_id},
            blocking=False,
        )
