"""Sensors for Spot The Aurora NZ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, NAME
from .coordinator import AuroraCoordinator
from .oval import tier_icon

MEASURE = SensorStateClass.MEASUREMENT


@dataclass(frozen=True, kw_only=True)
class AuroraSensorDescription(SensorEntityDescription):
    """Describes an aurora sensor."""

    value_key: str
    icon_fn: Callable[[Any], str] | None = None
    attrs_keys: tuple[str, ...] = ()


VISIBILITY_SENSORS: tuple[AuroraSensorDescription, ...] = (
    AuroraSensorDescription(
        key="visibility_now",
        name="Visibility now",
        value_key="tier_now",
        icon_fn=tier_icon,
        attrs_keys=("score_now",),
    ),
    AuroraSensorDescription(
        key="visibility_15m",
        name="Visibility 15 minutes",
        value_key="tier_15",
        icon_fn=tier_icon,
        attrs_keys=("score_15",),
    ),
    AuroraSensorDescription(
        key="visibility_30m",
        name="Visibility 30 minutes",
        value_key="tier_30",
        icon_fn=tier_icon,
        attrs_keys=("score_30",),
    ),
    AuroraSensorDescription(
        key="visibility_1h",
        name="Visibility 1 hour",
        value_key="tier_60",
        icon_fn=tier_icon,
        attrs_keys=("score_60",),
    ),
    AuroraSensorDescription(
        key="visibility_2h",
        name="Visibility 2 hours",
        value_key="tier_120",
        icon_fn=tier_icon,
        attrs_keys=("score_120",),
    ),
)

DATA_SENSORS: tuple[AuroraSensorDescription, ...] = (
    AuroraSensorDescription(
        key="aurora_score",
        name="Aurora score",
        value_key="score_now",
        native_unit_of_measurement="%",
        state_class=MEASURE,
        icon="mdi:weather-night",
        attrs_keys=(
            "oval_equatorward",
            "oval_poleward",
            "oval_view_line",
            "is_daylight",
            "status",
            "latitude",
            "longitude",
            "geomagnetic_latitude",
            "location_source",
        ),
    ),
    AuroraSensorDescription(
        key="substorm_score",
        name="Substorm score",
        value_key="substorm_score",
        native_unit_of_measurement="%",
        state_class=MEASURE,
        icon="mdi:chart-bell-curve",
        attrs_keys=("bay_onset", "cme_sheath", "summary"),
    ),
    AuroraSensorDescription(
        key="spot_score",
        name="Spot The Aurora score",
        value_key="spot_score",
        native_unit_of_measurement="%",
        state_class=MEASURE,
        icon="mdi:moon-waning-crescent",
    ),
    AuroraSensorDescription(
        key="substorm_level",
        name="Substorm level",
        value_key="level",
        icon="mdi:alert-decagram",
    ),
    AuroraSensorDescription(
        key="substorm_trend",
        name="Substorm trend",
        value_key="trend",
        icon="mdi:trending-up",
    ),
    AuroraSensorDescription(
        key="confidence",
        name="Forecast confidence",
        value_key="confidence",
        native_unit_of_measurement="%",
        icon="mdi:check-decagram",
    ),
    AuroraSensorDescription(
        key="bz",
        name="IMF Bz",
        value_key="bz",
        native_unit_of_measurement="nT",
        state_class=MEASURE,
        icon="mdi:magnet",
    ),
    AuroraSensorDescription(
        key="bt",
        name="IMF Bt",
        value_key="bt",
        native_unit_of_measurement="nT",
        state_class=MEASURE,
        icon="mdi:magnet-on",
    ),
    AuroraSensorDescription(
        key="bz_30m",
        name="IMF Bz 30m average",
        value_key="avg_30m_bz",
        native_unit_of_measurement="nT",
        state_class=MEASURE,
        icon="mdi:magnet",
    ),
    AuroraSensorDescription(
        key="by",
        name="IMF By 30m average",
        value_key="by",
        native_unit_of_measurement="nT",
        state_class=MEASURE,
        icon="mdi:magnet",
    ),
    AuroraSensorDescription(
        key="speed",
        name="Solar wind speed",
        value_key="speed",
        native_unit_of_measurement="km/s",
        state_class=MEASURE,
        icon="mdi:weather-windy",
    ),
    AuroraSensorDescription(
        key="density",
        name="Solar wind density",
        value_key="density",
        native_unit_of_measurement="p/cm³",
        state_class=MEASURE,
        icon="mdi:dots-hexagon",
    ),
    AuroraSensorDescription(
        key="pressure",
        name="Dynamic pressure",
        value_key="dynamic_pressure_nPa",
        native_unit_of_measurement="nPa",
        state_class=MEASURE,
        icon="mdi:gauge",
    ),
    AuroraSensorDescription(
        key="newell",
        name="Newell coupling",
        value_key="newell_coupling_now",
        native_unit_of_measurement="Wb/s",
        state_class=MEASURE,
        icon="mdi:sine-wave",
    ),
    AuroraSensorDescription(
        key="newell_30m",
        name="Newell coupling 30m average",
        value_key="newell_avg_30m",
        native_unit_of_measurement="Wb/s",
        state_class=MEASURE,
        icon="mdi:sine-wave",
        entity_registry_enabled_default=False,
    ),
    AuroraSensorDescription(
        key="newell_60m",
        name="Newell coupling 60m average",
        value_key="newell_avg_60m",
        native_unit_of_measurement="Wb/s",
        state_class=MEASURE,
        icon="mdi:sine-wave",
        entity_registry_enabled_default=False,
    ),
    AuroraSensorDescription(
        key="southward_30m",
        name="Southward minutes 30m",
        value_key="southward_minutes_30m",
        native_unit_of_measurement="min",
        state_class=MEASURE,
        icon="mdi:arrow-down-bold",
    ),
    AuroraSensorDescription(
        key="hemispheric_power",
        name="Hemispheric power",
        value_key="hemispheric_power",
        native_unit_of_measurement="GW",
        state_class=MEASURE,
        icon="mdi:flash",
    ),
    AuroraSensorDescription(
        key="moon_illumination",
        name="Moon illumination",
        value_key="moon_illumination",
        native_unit_of_measurement="%",
        icon="mdi:moon-waning-crescent",
    ),
    AuroraSensorDescription(
        key="l1_delay",
        name="L1 propagation delay",
        value_key="l1_delay",
        native_unit_of_measurement="min",
        icon="mdi:timer-sand",
        entity_registry_enabled_default=False,
    ),
    AuroraSensorDescription(
        key="oval_boundary",
        name="Oval equatorward boundary",
        value_key="oval_equatorward",
        native_unit_of_measurement="°",
        state_class=MEASURE,
        icon="mdi:map-marker-path",
        entity_registry_enabled_default=False,
    ),
    AuroraSensorDescription(
        key="kp_forecast",
        name="Kp forecast",
        value_key="kp_max_72h",
        icon="mdi:calendar-clock",
        attrs_keys=("kp_forecast", "kp_now", "kp_threshold"),
    ),
    AuroraSensorDescription(
        key="geomagnetic_latitude",
        name="Geomagnetic latitude",
        value_key="geomagnetic_latitude",
        native_unit_of_measurement="°",
        icon="mdi:map-marker",
        entity_registry_enabled_default=False,
        attrs_keys=("latitude", "longitude", "location_source"),
    ),
    AuroraSensorDescription(
        key="view_line",
        name="Visibility view line",
        value_key="oval_view_line",
        native_unit_of_measurement="°",
        state_class=MEASURE,
        icon="mdi:eye-outline",
        entity_registry_enabled_default=False,
    ),
)

SPACE_WEATHER_SENSORS: tuple[AuroraSensorDescription, ...] = (
    AuroraSensorDescription(
        key="cme_count",
        name="CME count",
        value_key="cme_count",
        icon="mdi:weather-sunny-alert",
        attrs_keys=("cmes", "latest_cme_speed"),
    ),
    AuroraSensorDescription(
        key="flare_count",
        name="Solar flare count",
        value_key="flare_count",
        icon="mdi:white-balance-sunny",
        attrs_keys=("flares", "latest_flare_class"),
    ),
    AuroraSensorDescription(
        key="xray_flux_long",
        name="X-ray flux (long band)",
        value_key="xray_flux_long",
        native_unit_of_measurement="W/m²",
        state_class=MEASURE,
        icon="mdi:flash-alert",
        attrs_keys=("xray_class", "xray_flux_short", "xray_time"),
    ),
    AuroraSensorDescription(
        key="proton_flux_solar1",
        name="Proton flux (SOLAR-1)",
        value_key="proton_solar1",
        native_unit_of_measurement="p/cm²·s·sr·MeV",
        state_class=MEASURE,
        icon="mdi:atom",
        attrs_keys=("proton_solar1_channels", "proton_solar1_time"),
        entity_registry_enabled_default=False,
    ),
    AuroraSensorDescription(
        key="proton_flux_ace",
        name="Proton flux (ACE)",
        value_key="proton_ace",
        native_unit_of_measurement="p/cm²·s·sr·MeV",
        state_class=MEASURE,
        icon="mdi:atom",
        attrs_keys=("proton_ace_channels", "proton_ace_time"),
        entity_registry_enabled_default=False,
    ),
    AuroraSensorDescription(
        key="proton_flux_imap",
        name="Proton flux (IMAP)",
        value_key="proton_imap",
        native_unit_of_measurement="p/cm²·s·sr·MeV",
        state_class=MEASURE,
        icon="mdi:atom",
        attrs_keys=("proton_imap_channels", "proton_imap_time"),
        entity_registry_enabled_default=False,
    ),
)

SIGHTING_SENSORS: tuple[AuroraSensorDescription, ...] = (
    AuroraSensorDescription(
        key="sightings_count",
        name="Aurora sightings today",
        value_key="sightings_count",
        icon="mdi:account-eye",
        attrs_keys=("sightings", "sightings_visible_count"),
    ),
    AuroraSensorDescription(
        key="closest_sighting_distance",
        name="Closest sighting distance",
        value_key="closest_sighting_distance_km",
        native_unit_of_measurement="km",
        state_class=MEASURE,
        icon="mdi:map-marker-distance",
        attrs_keys=("closest_sighting",),
    ),
    AuroraSensorDescription(
        key="closest_sighting_latitude_delta",
        name="Closest sighting latitude difference",
        value_key="closest_sighting_latitude_delta_deg",
        native_unit_of_measurement="°",
        state_class=MEASURE,
        icon="mdi:latitude",
        attrs_keys=("closest_sighting", "closest_sighting_latitude_delta_km"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: AuroraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AuroraSensor(coordinator, entry, desc)
        for desc in VISIBILITY_SENSORS
        + DATA_SENSORS
        + SPACE_WEATHER_SENSORS
        + SIGHTING_SENSORS
    ]
    async_add_entities(entities)


class AuroraSensor(CoordinatorEntity[AuroraCoordinator], SensorEntity):
    """A single aurora sensor."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    entity_description: AuroraSensorDescription

    def __init__(
        self,
        coordinator: AuroraCoordinator,
        entry: ConfigEntry,
        description: AuroraSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="TNR Protography",
            model="Aurora Forecast",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.spottheaurora.co.nz",
        )

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.value_key)

    @property
    def icon(self) -> str | None:
        if self.entity_description.icon_fn and self.native_value is not None:
            return self.entity_description.icon_fn(self.native_value)
        return self.entity_description.icon

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self.coordinator.data or not self.entity_description.attrs_keys:
            return None
        out = {
            key: self.coordinator.data.get(key)
            for key in self.entity_description.attrs_keys
        }
        # The forecast card reads these under shorter names
        if "kp_forecast" in out:
            out["forecast"] = out.pop("kp_forecast")
        if "kp_threshold" in out:
            out["threshold"] = out.pop("kp_threshold")
        return out
