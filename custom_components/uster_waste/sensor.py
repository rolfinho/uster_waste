"""Sensor platform for Uster Waste."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    ATTR_NEXT_COLLECTION,
    ATTR_DATE,
    ATTR_TYPE,
    ATTR_DAYS_UNTIL,
    ATTR_ENTRIES,
    ATTR_ERROR,
    MANUAL_REFRESH,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(days=1)

# Swiss date helpers
MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mrz": "03", "Mär": "03",
    "Apr": "04", "Mai": "05", "Jun": "06", "Jul": "07",
    "Aug": "08", "Sep": "09", "Okt": "10", "Nov": "11", "Dez": "12"
}


def _parse_date(date_str: str) -> Optional[datetime]:
    """Convert Swiss date string (e.g., '24.10.2023' or '24. Okt. 2023') to datetime."""
    date_str = date_str.strip()
    # Normalize Swiss month abbreviations
    for key, value in MONTH_MAP.items():
        date_str = date_str.replace(key, value)
    # Try formats: dd.mm.yyyy, d.m.yy
    for fmt in ["%d.%m.%Y", "%d.%m.%y"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    _LOGGER.warning(f"Could not parse date: '{date_str}'")
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor."""
    config = entry.data
    token = config["token"]
    waste_id = config["id"]
    name = config.get("name", "Uster Waste")

    entity = UsterWasteSensor(
        entry_id=entry.entry_id,
        token=token,
        waste_id=waste_id,
        name=name
    )
    async_add_entities([entity])


class UsterWasteDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Fetch data from Uster website."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        token: str,
        waste_id: str,
    ):
        super().__init__(hass, _LOGGER, name="Uster Waste", update_interval=SCAN_INTERVAL)
        self.session = session
        self.token = token
        self.waste_id = waste_id
        self.data = None
        self.last_error = None
        self.last_updated = None

    async def async_update(self) -> dict:
        """Fetch data (cache if valid)."""
        # 1. Check cache (valid for 24h)
        if self.last_updated and (datetime.now() - self.last_updated) < SCAN_INTERVAL:
            return self.data

        url = (
            "https://www.uster.ch/abfallstrassenabschnitt"
            f"?strassenabschnitt%5B_token%5D={self.token}"
            f"&strassenabschnitt%5BstrassenabschnittId%5D={self.waste_id}"
        )

        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 403 or response.status == 404:
                    raise Exception(
                        "Token expired or invalid. "
                        "Please get a fresh URL from https://www.uster.ch/abfallstrassenabschnitt"
                    )
                response.raise_for_status()
                html = await response.text()

            # Parse HTML
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", class_="table table-striped")
            if not table:
                table = soup.find("table")
                if not table:
                    raise ValueError("No table found on page.")

            rows = table.find_all("tr")
            if len(rows) < 2:
                raise ValueError("Table has no data rows.")

            entries = []
            now = datetime.now()

            for row in rows[1:4]:  # Next 3 entries
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue

                collection_type = cols[0].get_text(strip=True)
                date_str = cols[1].get_text(strip=True).replace(" \u00a0", " ")  # Clean no-break space
                dt = _parse_date(date_str)
                if not dt:
                    _LOGGER.warning(f"Skipping row with invalid date: {date_str}")
                    continue

                entries.append({
                    "Sammlung": collection_type,
                    "Wann?": date_str,
                    "date_obj": dt,
                    "days_until": (dt - now).days
                })

            # Sort by date (ascending)
            entries.sort(key=lambda x: x["date_obj"])

            self.data = {
                "next_collection": entries[0]["Sammlung"] if entries else None,
                "date": entries[0]["Wann?"] if entries else None,
                "type": entries[0]["Sammlung"] if entries else None,
                "days_until": entries[0]["days_until"] if entries else None,
                "entries": [
                    {
                        "type": e["Sammlung"],
                        "date": e["Wann?"],
                        "days_until": e["days_until"]
                    }
                    for e in entries[:3]
                ]
            }
            self.last_updated = datetime.now()

        except Exception as e:
            _LOGGER.error("Error fetching Uster data: %s", e)
            self.data = {
                ATTR_ERROR: str(e),
                "next_collection": None,
                "date": None,
                "entries": []
            }
            self.last_error = str(e)

        return self.data


class UsterWasteSensor(SensorEntity):
    """Uster Waste Sensor Entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:recycle"
    _attr_device_class = None

    def __init__(
        self,
        entry_id: str,
        token: str,
        waste_id: str,
        name: str
    ):
        self._entry_id = entry_id
        self.token = token
        self.waste_id = waste_id
        self._attr_name = f"{name} Schedule"
        self._attr_unique_id = f"uster_waste_{entry_id}"
        self._attr_extra_state_attributes = {
            ATTR_ENTRIES: [],
        }
        self.data = None

    async def async_update(self):
        """Update sensor state."""
        # Fetch fresh data
        data = await self._fetch_data()
        self.data = data
        self._attr_native_value = len(data.get("entries", []))
        self._attr_extra_state_attributes.update(
            {
                ATTR_NEXT_COLLECTION: data.get("next_collection"),
                ATTR_DATE: data.get("date"),
                ATTR_TYPE: data.get("type"),
                ATTR_DAYS_UNTIL: data.get("days_until"),
                ATTR_ENTRIES: data.get("entries", []),
                ATTR_ERROR: data.get("error")
            }
        )

    async def _fetch_data(self) -> dict:
        """Fetch data from Uster website."""
        try:
            session = async_get_clientsession(self.hass)
            url = (
                "https://www.uster.ch/abfallstrassenabschnitt"
                f"?strassenabschnitt%5B_token%5D={self.token}"
                f"&strassenabschnitt%5BstrassenabschnittId%5D={self.waste_id}"
            )

            async with session.get(url, timeout=10) as response:
                if response.status == 403 or response.status == 404:
                    raise Exception(
                        "Token expired or invalid. "
                        "Please get a fresh URL from https://www.uster.ch/abfallstrassenabschnitt"
                    )
                response.raise_for_status()
                html = await response.text()

            # Parse HTML
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", class_="table table-striped")
            if not table:
                table = soup.find("table")
                if not table:
                    raise ValueError("No table found on page.")

            rows = table.find_all("tr")
            if len(rows) < 2:
                raise ValueError("Table has no data rows.")

            entries = []
            now = datetime.now()

            for row in rows[1:4]:  # Next 3 entries
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue

                collection_type = cols[0].get_text(strip=True)
                date_str = cols[1].get_text(strip=True).replace("  ", " ")  # Clean no-break space
                dt = _parse_date(date_str)
                if not dt:
                    _LOGGER.warning(f"Skipping row with invalid date: {date_str}")
                    continue

                entries.append({
                    "Sammlung": collection_type,
                    "Wann?": date_str,
                    "date_obj": dt,
                    "days_until": (dt - now).days
                })

            # Sort by date (ascending)
            entries.sort(key=lambda x: x["date_obj"])

            return {
                "next_collection": entries[0]["Sammlung"] if entries else None,
                "date": entries[0]["Wann?"] if entries else None,
                "type": entries[0]["Sammlung"] if entries else None,
                "days_until": entries[0]["days_until"] if entries else None,
                "entries": [
                    {
                        "type": e["Sammlung"],
                        "date": e["Wann?"],
                        "days_until": e["days_until"]
                    }
                    for e in entries[:3]
                ]
            }
        except Exception as e:
            _LOGGER.error("Error fetching Uster data: %s", e)
            return {
                ATTR_ERROR: str(e),
                "next_collection": None,
                "date": None,
                "entries": []
            }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Force first update
        await self.async_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_updated is not None

    async def async_press(self):
        """Handle the button press (manual refresh)."""
        await self.async_update()
        self.async_write_ha_state()
