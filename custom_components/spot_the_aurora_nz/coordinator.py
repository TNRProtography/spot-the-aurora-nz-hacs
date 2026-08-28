"""Data coordinator for Spot The Aurora NZ."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LOCATION,
    CONF_LOCATION_MODE,
    CONF_TRACKED_ENTITY,
    DOMAIN,
    FORECAST_URL,
    KP_FORECAST_URL,
    MODE_ENTITY,
    MODE_HOME,
    MODE_PIN,
    RTSW_URL,
    SUBSTORM_URL,
)
from .oval import (
    compute_oval_boundary,
    geo_to_gmag_lat,
    kp_threshold_for_latitude,
    location_adjusted_score,
    project_scores,
    visibility_line,
    visibility_tier,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 20


class AuroraCoordinator(DataUpdateCoordinator):
    """Polls both workers once and shares the result with every entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        options: dict[str, Any],
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self._options = options
        self.latitude: float | None = None
        self.longitude: float | None = None
        self.location_source: str = "unknown"
        self._session = async_get_clientsession(hass)
        self._forecast_cache: dict[str, Any] = {}
        self._kp_cache: list[dict[str, Any]] = []
        self._tick = 0

    def _resolve_location(self) -> None:
        """Work out where the user is, per update.

        Home and pin modes are fixed. Entity mode re-reads the tracker every
        cycle, so the forecast follows a phone that drives to a dark site.
        """
        mode = self._options.get(CONF_LOCATION_MODE, MODE_HOME)

        if mode == MODE_ENTITY:
            entity_id = self._options.get(CONF_TRACKED_ENTITY)
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is not None:
                lat = state.attributes.get("latitude")
                lon = state.attributes.get("longitude")
                if lat is not None and lon is not None:
                    self.latitude = float(lat)
                    self.longitude = float(lon)
                    self.location_source = entity_id
                    return
            # Tracker unavailable or has no fix - fall back to home rather
            # than losing the forecast entirely.
            _LOGGER.debug("Tracker %s has no location; using home", entity_id)
            self.latitude = self.hass.config.latitude
            self.longitude = self.hass.config.longitude
            self.location_source = "home (tracker unavailable)"
            return

        if mode == MODE_PIN:
            loc = self._options.get(CONF_LOCATION) or {}
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            if lat is not None and lon is not None:
                self.latitude = float(lat)
                self.longitude = float(lon)
                self.location_source = "pin"
                return

        self.latitude = self.hass.config.latitude
        self.longitude = self.hass.config.longitude
        self.location_source = "home"

    async def _fetch(self, url: str) -> Any:
        try:
            async with async_timeout.timeout(TIMEOUT):
                resp = await self._session.get(url)
                if resp.status != 200:
                    _LOGGER.debug("%s returned HTTP %s", url, resp.status)
                    return None
                return await resp.json(content_type=None)
        except (asyncio.TimeoutError, Exception) as err:  # noqa: BLE001
            _LOGGER.debug("Fetch failed for %s: %s", url, err)
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        self._tick += 1
        self._resolve_location()

        tasks = [self._fetch(SUBSTORM_URL), self._fetch(RTSW_URL)]
        # NOAA reissues the Kp forecast a few times a day, so poll it rarely.
        want_kp = self._tick % 10 == 1 or not self._kp_cache
        # The composite forecast payload is large; poll it half as often.
        want_forecast = self._tick % 2 == 1 or not self._forecast_cache
        if want_forecast:
            tasks.append(self._fetch(FORECAST_URL))
        if want_kp:
            tasks.append(self._fetch(KP_FORECAST_URL))

        results = await asyncio.gather(*tasks)
        substorm = results[0]
        rtsw = results[1]
        idx = 2
        if want_forecast:
            if results[idx]:
                self._forecast_cache = results[idx]
            idx += 1
        if want_kp and results[idx]:
            self._kp_cache = _parse_kp_forecast(results[idx])
        forecast = self._forecast_cache

        if not substorm and not forecast:
            raise UpdateFailed("No data from either upstream service")

        return self._build(substorm, rtsw, forecast)

    # ------------------------------------------------------------------

    def _build(
        self, substorm: Any, rtsw: Any, forecast: Any
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}

        current = (substorm or {}).get("current") or {}
        metrics = (substorm or {}).get("metrics") or {}
        sw = metrics.get("solar_wind") or {}

        data["substorm_score"] = _f(current.get("score"), 0.0)
        data["level"] = current.get("level")
        data["trend"] = current.get("risk_trend")
        data["confidence"] = current.get("confidence")
        data["summary"] = current.get("summary")
        data["bay_onset"] = bool(current.get("bay_onset_flag"))
        data["cme_sheath"] = bool(current.get("cme_sheath_flag"))
        data["l1_delay"] = _f(substorm.get("l1_propagation_minutes") if substorm else None)

        for key in (
            "bz",
            "bt",
            "avg_30m_bz",
            "speed",
            "density",
            "dynamic_pressure_nPa",
            "avg_30m_pressure_nPa",
            "newell_coupling_now",
            "newell_avg_30m",
            "newell_avg_60m",
            "southward_minutes_30m",
            "southward_minutes_60m",
            "temperature_K",
        ):
            data[key] = _f(sw.get(key))

        # IMF By from the RTSW feed, averaged over 30 minutes for the RM term
        data["by"] = _avg_by_30m(rtsw)

        # Composite forecast
        cf = (forecast or {}).get("currentForecast") or {}
        data["spot_score"] = _f(cf.get("spotTheAuroraForecast"))
        data["hemispheric_power"] = _f((cf.get("inputs") or {}).get("hemisphericPower"))
        moon = cf.get("moon") or {}
        data["moon_illumination"] = _f(moon.get("illumination"))
        sun = cf.get("sun") or {}
        data["sun_rise"] = sun.get("rise")
        data["sun_set"] = sun.get("set")

        # --- Oval geometry ---------------------------------------------
        boundary = compute_oval_boundary(
            newell_avg_60m=data.get("newell_avg_60m"),
            newell_avg_30m=data.get("newell_avg_30m"),
            pressure_npa=data.get("avg_30m_pressure_nPa")
            or data.get("dynamic_pressure_nPa"),
            by=data.get("by"),
            bz=data.get("bz"),
            bay_onset=data["bay_onset"],
        )
        data["oval_equatorward"] = round(boundary, 3)
        data["oval_poleward"] = -69.0
        data["oval_view_line"] = round(
            visibility_line(boundary, data["substorm_score"]), 3
        )

        # --- Daylight --------------------------------------------------
        sun_state = self.hass.states.get("sun.sun")
        is_daylight = sun_state is not None and sun_state.state == "above_horizon"
        data["is_daylight"] = is_daylight

        # --- Projections, location adjusted ----------------------------
        proj = project_scores(
            score=data["substorm_score"],
            level=data["level"],
            trend=data["trend"],
            newell_now=data.get("newell_coupling_now"),
            newell_avg_30m=data.get("newell_avg_30m"),
            confidence=data.get("confidence"),
        )
        data["status"] = proj["status"]

        def adjust(raw: float) -> float:
            if is_daylight:
                return 0.0
            return location_adjusted_score(
                raw, self.latitude, self.longitude, boundary
            )

        data["score_now"] = round(adjust(data["substorm_score"]), 1)
        data["score_15"] = round(adjust(proj["score_15"]), 1)
        data["score_30"] = round(adjust(proj["score_30"]), 1)
        data["score_60"] = round(adjust(proj["score_60"]), 1)
        data["score_120"] = round(adjust(data.get("spot_score") or 0.0), 1)

        for slot in ("now", "15", "30", "60", "120"):
            data[f"tier_{slot}"] = visibility_tier(data[f"score_{slot}"])

        data["kp_forecast"] = self._kp_cache
        data["kp_now"] = self._kp_cache[0]["kp"] if self._kp_cache else None
        data["kp_max_72h"] = (
            max((e["kp"] for e in self._kp_cache), default=None)
            if self._kp_cache
            else None
        )

        data["latitude"] = self.latitude
        data["longitude"] = self.longitude
        data["location_source"] = self.location_source
        if self.latitude is not None and self.longitude is not None:
            gmag = geo_to_gmag_lat(self.latitude, self.longitude)
            data["geomagnetic_latitude"] = round(gmag, 2)
            data["kp_threshold"] = round(kp_threshold_for_latitude(gmag), 1)

        return data


def _f(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        out = float(value)
        return out
    except (TypeError, ValueError):
        return default


def _avg_by_30m(rtsw: Any) -> float | None:
    """30-minute average of IMF By from the RTSW merged feed."""
    rows = None
    if isinstance(rtsw, list):
        rows = rtsw
    elif isinstance(rtsw, dict) and isinstance(rtsw.get("data"), list):
        rows = rtsw["data"]
    if not rows:
        return None

    vals = [
        _f(r.get("by"))
        for r in rows[-30:]
        if isinstance(r, dict) and _f(r.get("by")) is not None
    ]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _parse_kp_forecast(raw: Any) -> list[dict[str, Any]]:
    """NOAA returns a header row then [time_tag, kp, observed, noaa_scale]."""
    if not isinstance(raw, list) or len(raw) < 2:
        return []

    out: list[dict[str, Any]] = []
    for row in raw[1:]:
        if not isinstance(row, list) or len(row) < 3:
            continue
        try:
            time_tag = str(row[0]).replace(" ", "T")
            if not time_tag.endswith("Z"):
                time_tag += "Z"
            kp = float(row[1])
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "t": time_tag,
                "kp": round(kp, 2),
                "observed": str(row[2]).lower() if len(row) > 2 else "predicted",
            }
        )
    return out
