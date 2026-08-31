"""Aurora sightings ("reportings") as geo_location events.

Each community-submitted sighting becomes a transient geo_location entity,
the same way NSW Rural Fire Service or USGS earthquake feeds work in core
Home Assistant. That makes them show up automatically on any Lovelace map
card with `geo_location_sources: [spot_the_aurora_nz]` (or `all`), and gives
each one a `distance` state - in kilometres from wherever this integration
is configured to think you are - for `numeric_state` automations.

Sightings are re-synced every time the coordinator refreshes: reports the
coordinator has already dropped (because they are from before the last NZ
midday - see spacedata.nz_midday_cutoff_utc) simply stop being recreated
here, so the map and the entity list empty out at the same time the site's
own reportings would.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTRIBUTION, DOMAIN
from .coordinator import AuroraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sightings geo_location feed."""
    coordinator: AuroraCoordinator = hass.data[DOMAIN][entry.entry_id]
    manager = _SightingsManager(hass, coordinator, async_add_entities)
    entry.async_on_unload(coordinator.async_add_listener(manager.async_sync))
    manager.async_sync()


class _SightingsManager:
    """Keeps one geo_location entity alive per currently-visible sighting."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AuroraCoordinator,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._entities: dict[str, AuroraSightingEvent] = {}

    @callback
    def async_sync(self) -> None:
        sightings = (self._coordinator.data or {}).get("sightings") or []
        current_ids = {s["id"] for s in sightings}

        for sighting_id in list(self._entities):
            if sighting_id not in current_ids:
                entity = self._entities.pop(sighting_id)
                self._hass.async_create_task(entity.async_remove(force_remove=True))

        new_entities: list[AuroraSightingEvent] = []
        for sighting in sightings:
            sighting_id = sighting["id"]
            existing = self._entities.get(sighting_id)
            if existing is not None:
                existing.update_sighting(sighting)
                continue
            entity = AuroraSightingEvent(sighting)
            self._entities[sighting_id] = entity
            new_entities.append(entity)

        if new_entities:
            self._async_add_entities(new_entities)


class AuroraSightingEvent(GeolocationEvent):
    """One aurora sighting report, placed on the map."""

    _attr_should_poll = False
    _attr_source = DOMAIN
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_attribution = ATTRIBUTION

    def __init__(self, sighting: dict[str, Any]) -> None:
        self._sighting = sighting

    def update_sighting(self, sighting: dict[str, Any]) -> None:
        self._sighting = sighting
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def name(self) -> str:
        return f"{self._sighting['emoji']} {self._sighting['name']}"

    @property
    def latitude(self) -> float | None:
        return self._sighting.get("latitude")

    @property
    def longitude(self) -> float | None:
        return self._sighting.get("longitude")

    @property
    def distance(self) -> float | None:
        return self._sighting.get("distance_km")

    @property
    def icon(self) -> str:
        status = self._sighting.get("status", "")
        if status == "cloudy":
            return "mdi:weather-cloudy"
        if status.startswith("nothing"):
            return "mdi:eye-off-outline"
        return "mdi:eye"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._sighting
        return {
            "status": s.get("status"),
            "status_label": s.get("status_label"),
            "reported_at": s.get("reported_at"),
            "latitude_delta_deg": s.get("latitude_delta_deg"),
            "latitude_delta_km": s.get("latitude_delta_km"),
        }
