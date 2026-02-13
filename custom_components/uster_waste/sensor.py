"""Uster Waste Sensor."""
import logging
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MANUAL_REFRESH_SERVICE

_LOGGER = logging.getLogger(__name__)

# ✅ CORRECTED URL FORMAT (no %5B, no extra encoded brackets)
BASE_URL = "https://www.uster.ch/abfallstrassenabschnitt"

# For Swiss date parsing
MONTHS = {
    "Jan": "01", "Feb": "02", "Mrz": "03", "Mär": "03",
    "Apr": "04", "Mai": "05", "Jun": "06", "Jul": "07",
    "Aug": "08", "Sep": "09", "Okt": "10", "Nov": "11", "Dez": "12"
}


def parse_swiss_date(date_str: str) -> Optional[datetime]:
    """Parse Swiss date like '24. Okt. 2023' or '24.10.2023'."""
    date_str = date_str.strip()
    if not date_str:
        return None
    # Replace Swiss months (e.g., "Okt" → "10")
    for swiss, num in MONTHS.items():
        date_str = date_str.replace(swiss, num)
    # Clean extra spaces/dots
    date_str = re.sub(r'\.\s*\.', '.', date_str)
    # Try multiple formats
    for fmt in ["%d.%m.%Y", "%d.%m.%y"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    _LOGGER.warning(f"Failed to parse date: {date_str}")
    return None


class UsterWasteDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Fetch and cache Uster waste data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self.token = entry.data["token"]
        self.id = entry.data["id"]
        self.name = entry.data.get("name", "Uster Waste")
        # ✅ CORRECT URL:
        self.url = f"{BASE_URL}?token={self.token}&strassenabschnittId={self.id}"
        super().__init__(hass, _LOGGER, name="uster_waste", update_interval=timedelta(days=1))

    async def _async_update_data(self) -> dict:
        """Fetch the latest data from Uster."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(self.url, timeout=10) as resp:
                if resp.status != 200:
                    raise UpdateFailed(
                        f"HTTP {resp.status} — check token & ID (token may be expired)."
                        "Get a fresh URL from https://www.uster.ch/abfallstrassenabschnitt"
                    )
                html = await resp.text()
        except aiohttp.ClientError as e:
            raise UpdateFailed(f"Network error: {e}") from e

        # Parse HTML
        soup = BeautifulSoup(html, "html.parser")

        # Find the table (robust: class="table table-striped" or any <table>)
        table = soup.find("table", class_="table table-striped") or soup.find("table")
        if not table:
            raise UpdateFailed("No waste schedule table found on Uster.ch page.")

        rows = table.find_all("tr")
        if len(rows) < 2:
            raise UpdateFailed("Table has no data rows — check page layout changed.")

        now = datetime.now()
        entries = []

        for row in rows[1:4]:  # First 3 data rows
            cols = row.find_all("td")
            if len(cols) < 2:
                continue

            collection = cols[0].get_text(strip=True)
            date_str = cols[1].get_text(strip=True)

            dt = parse_swiss_date(date_str)
            if not dt:
                _LOGGER.warning(f"Skipping row: invalid date '{date_str}'")
                continue

            entries.append({
                "type": collection,
                "date": date_str,
                "days_until": (dt - now).days
            })

        if not entries:
            raise UpdateFailed("No valid dates found in table.")

        # Sort ascending by date
        entries.sort(key=lambda x: x["date"])

        return {
            "next_collection": entries[0]["type"],
            "date": entries[0]["date"],
            "days_until": entries[0]["days_until"],
            "entries": entries,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor."""
    coordinator: UsterWasteDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([UsterWasteSensor(entry, coordinator)], update_before_add=True)


class UsterWasteSensor(SensorEntity):
    """Uster Waste Collection Sensor."""

    _attr_has_entity_name = True
    _attr_name = None  # Use coordinator name
    _attr_icon = "mdi:recycle"
    _attr_native_unit_of_measurement = "days" if "days_until" else None

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: UsterWasteDataUpdateCoordinator,
    ):
        self.coordinator = coordinator
        self._attr_unique_id = f"uster_waste_{entry.entry_id}"
        self._attr_device_info = {
            "name": coordinator.name,
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def native_value(self) -> Optional[str]:
        """Return next collection type."""
        return self.coordinator.data.get("next_collection")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extended attributes."""
        data = self.coordinator.data or {}
        return {
            "date": data.get("date"),
            "days_until": data.get("days_until"),
            "entries": data.get("entries", []),
            "url": self.coordinator.url,  # For debugging
        }

    async def async_update(self) -> None:
        """Manually trigger update (used by refresh service)."""
        await self.coordinator.async_request_refresh()