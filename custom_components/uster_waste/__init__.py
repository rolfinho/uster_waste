"""Uster Waste integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, MANUAL_REFRESH_SERVICE
from .sensor import UsterWasteDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Uster Waste from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    # Set up coordinator *once per entry*
    coordinator = UsterWasteDataUpdateCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register manual refresh service
    async def handle_refresh(call):
        entry_id = call.data.get("entry_id", entry.entry_id)
        coord = hass.data[DOMAIN].get(entry_id)
        if coord:
            await coord.async_request_refresh()
        else:
            hass.components.persistent_notification.create(
                "Uster Waste: No active entry found. Reload the integration.",
                title="Uster Waste Error"
            )

    hass.services.async_register(DOMAIN, MANUAL_REFRESH_SERVICE, handle_refresh)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    hass.services.async_remove(DOMAIN, MANUAL_REFRESH_SERVICE)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)