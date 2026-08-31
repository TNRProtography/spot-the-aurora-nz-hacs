"""Data coordinator for Spot The Aurora NZ."""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CME_URL,
    CONF_LOCATION,
    CONF_LOCATION_MODE,
    CONF_TRACKED_ENTITY,
    DOMAIN,
    EPAM_BASE,
    FLARE_URL,
    FORECAST_URL,
    KP_FORECAST_URL,
    MODE_ENTITY,
    MODE_HOME,
    MODE_PIN,
    PROTON_SOURCES,
    RTSW_URL,
    SIGHTINGS_POLL_TICKS,
    SIGHTINGS_URL,
    SLOW_POLL_TICKS,
    SUBSTORM_URL,
    XRAY_URL,
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
from .spacedata import (
    process_cme_data,
    process_flare_data,
    process_proton_source,
    process_sightings,
    process_xray,
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
        self._cme_cache: list[dict[str, Any]] = []
        self._flare_cache: list[dict[str, Any]] = []
        self._xray_cache: dict[str, Any] = {}
        self._proton_cache: dict[str, dict[str, Any] | None] = {}
        self._sightings_raw: list[Any] = []
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

    async def _fetch(self, url: str, label: str = "") -> Any:
        """GET and decode JSON. Returns None on any failure, and says why.

        Some upstreams serve JSON as text/plain, so content_type is not
        enforced. A few reject requests without a User-Agent.
        """
        name = label or url
        try:
            async with asyncio.timeout(TIMEOUT):
                resp = await self._session.get(
                    url, headers={"User-Agent": "HomeAssistant-SpotTheAuroraNZ"}
                )
                if resp.status != 200:
                    _LOGGER.warning("%s returned HTTP %s", name, resp.status)
                    return None
                return await resp.json(content_type=None)
        except asyncio.TimeoutError:
            _LOGGER.warning("%s timed out after %ss", name, TIMEOUT)
            return None
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("%s failed: %s: %s", name, type(err).__name__, err)
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        self._tick += 1
        self._resolve_location()

        jobs: dict[str, Any] = {
            "substorm": self._fetch(SUBSTORM_URL, "Substorm worker"),
            "rtsw": self._fetch(RTSW_URL, "RTSW solar wind"),
        }
        # NOAA reissues the Kp forecast a few times a day, so poll it rarely -
        # retry every cycle until we have data, then settle down.
        want_kp = not self._kp_cache or self._tick % 10 == 1
        # The composite forecast payload is large; poll it half as often.
        want_forecast = self._tick % 2 == 1 or not self._forecast_cache
        # CMEs, flares and X-ray/proton flux change on the order of minutes
        # to hours, not seconds - poll them rarely too.
        want_slow = not self._cme_cache or self._tick % SLOW_POLL_TICKS == 1
        want_sightings = self._tick % SIGHTINGS_POLL_TICKS == 1
        if want_forecast:
            jobs["forecast"] = self._fetch(FORECAST_URL, "Spot The Aurora forecast")
        if want_kp:
            jobs["kp"] = self._fetch(KP_FORECAST_URL, "NOAA Kp forecast")
        if want_slow:
            jobs["cme"] = self._fetch(CME_URL, "NASA DONKI CME")
            jobs["flare"] = self._fetch(FLARE_URL, "NASA DONKI FLR")
            jobs["xray"] = self._fetch(XRAY_URL, "GOES X-ray flux")
            for source in PROTON_SOURCES:
                jobs[f"proton_{source}"] = self._fetch(
                    f"{EPAM_BASE}/epam/raw?source={source}", f"EPAM {source}"
                )
        if want_sightings:
            jobs["sightings"] = self._fetch(SIGHTINGS_URL, "Aurora sightings")

        keys = list(jobs)
        results = await asyncio.gather(*(jobs[key] for key in keys))
        by_key = dict(zip(keys, results))

        substorm = by_key["substorm"]
        rtsw = by_key["rtsw"]

        if want_forecast and by_key.get("forecast"):
            self._forecast_cache = by_key["forecast"]
        forecast = self._forecast_cache

        if want_kp:
            parsed = _parse_kp_forecast(by_key.get("kp"))
            if parsed:
                if not self._kp_cache:
                    _LOGGER.info("Kp forecast loaded: %s entries", len(parsed))
                self._kp_cache = parsed
            elif by_key.get("kp") is not None:
                _LOGGER.warning(
                    "NOAA Kp forecast returned an unexpected shape: %.200s",
                    by_key["kp"],
                )

        if want_slow:
            self._cme_cache = process_cme_data(by_key.get("cme"))
            self._flare_cache = process_flare_data(by_key.get("flare"))
            self._xray_cache = process_xray(by_key.get("xray"))
            self._proton_cache = {
                source: process_proton_source(by_key.get(f"proton_{source}"))
                for source in PROTON_SOURCES
            }

        if want_sightings and by_key.get("sightings") is not None:
            self._sightings_raw = by_key["sightings"]

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

        # --- CMEs and flares --------------------------------------------
        data["cmes"] = self._cme_cache
        data["cme_count"] = len(self._cme_cache)
        data["latest_cme_speed"] = (
            self._cme_cache[0]["speed_km_s"] if self._cme_cache else None
        )

        data["flares"] = self._flare_cache
        data["flare_count"] = len(self._flare_cache)
        data["latest_flare_class"] = (
            self._flare_cache[0]["class_type"] if self._flare_cache else None
        )

        # --- X-ray flux ----------------------------------------------------
        data.update(self._xray_cache)

        # --- Proton flux, per L1 spacecraft --------------------------------
        for source in PROTON_SOURCES:
            reading = self._proton_cache.get(source)
            data[f"proton_{source}"] = reading["value"] if reading else None
            data[f"proton_{source}_channels"] = reading["channels"] if reading else None
            data[f"proton_{source}_time"] = reading["time_tag"] if reading else None

        # --- Aurora sightings ("reportings") --------------------------------
        sightings = process_sightings(self._sightings_raw, self.latitude, self.longitude)
        data["sightings"] = sightings
        data["sightings_count"] = len(sightings)
        data["sightings_visible_count"] = sum(
            1 for s in sightings if s["is_visible_sighting"]
        )
        closest = None
        if sightings and self.latitude is not None and self.longitude is not None:
            closest = min(sightings, key=lambda s: s.get("distance_km", math.inf))
        data["closest_sighting"] = closest
        data["closest_sighting_distance_km"] = (
            closest.get("distance_km") if closest else None
        )
        data["closest_sighting_latitude_delta_deg"] = (
            closest.get("latitude_delta_deg") if closest else None
        )
        data["closest_sighting_latitude_delta_km"] = (
            closest.get("latitude_delta_km") if closest else None
        )

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
    """Parse NOAA's planetary Kp forecast.

    NOAA has served this product in two different shapes over time, and
    switches between them without notice:

      - array-of-arrays, with a header row: [["time_tag","kp",...], [v, v, ...], ...]
      - array-of-objects: [{"time_tag": ..., "kp": ..., "observed": ..., "noaa_scale": ...}, ...]

    Handle both, the same way the web app's KpForecastTimeline does.
    """
    if not isinstance(raw, list) or not raw:
        return []

    is_objects = isinstance(raw[0], dict)
    rows = raw if is_objects else raw[1:]

    out: list[dict[str, Any]] = []
    for row in rows:
        if is_objects:
            if not isinstance(row, dict):
                continue
            time_raw = row.get("time_tag")
            kp_raw = row.get("kp")
            observed_raw = row.get("observed")
        else:
            if not isinstance(row, list) or len(row) < 2:
                continue
            time_raw = row[0]
            kp_raw = row[1]
            observed_raw = row[2] if len(row) > 2 else None

        if time_raw is None or kp_raw is None:
            continue
        try:
            time_tag = str(time_raw).replace(" ", "T")
            if not time_tag.endswith("Z"):
                time_tag += "Z"
            kp = float(kp_raw)
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "t": time_tag,
                "kp": round(kp, 2),
                "observed": str(observed_raw).lower() if observed_raw else "predicted",
            }
        )
    return out