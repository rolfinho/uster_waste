"""Uster Waste integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform, SERVICE_UPDATE_ENTITY

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Uster Waste from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    # Register manual refresh service
    hass.services.async_register(
        DOMAIN, 
        entry.data.get("name", "uster_waste"), 
        async_handle_manual_refresh
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_handle_manual_refresh(service):
    """Handle manual refresh service call."""
    entry_id = service.data.get("entry_id")
    if not entry_id or entry_id not in hass.data[DOMAIN]:
        return

    # Trigger update for all sensors under this entry
    await hass.services.async_call(
        "homeassistant", "update_entity",
        {"entity_id": [f"sensor.uster_waste_{entry_id}"]},
        blocking=False,
    )
