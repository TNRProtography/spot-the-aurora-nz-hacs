"""CMEs, flares, X-ray/proton flux and aurora sightings.

Ported from the Spot The Aurora web app's services/nasaService.ts,
UnifiedDashboardMode.tsx (X-ray) and AuroraSightings.tsx (reportings), so
this integration's numbers and lists agree with the app's.
"""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone
from typing import Any

from homeassistant.util import dt as dt_util

PROTON_CHANNELS: tuple[tuple[str, str], ...] = (
    ("p1", "47-68 keV"),
    ("p3", "115-195 keV"),
    ("p5", "310-580 keV"),
    ("p7", "795-1193 keV"),
    ("p8", "1-1.9 MeV"),
)

STATUS_EMOJI: dict[str, str] = {
    "eye": "\U0001f441️",
    "phone": "\U0001f4f1",
    "dslr": "\U0001f4f7",
    "cloudy": "☁️",
    "nothing-eye": "❌\U0001f441️",
    "nothing-phone": "❌\U0001f4f1",
    "nothing-dslr": "❌\U0001f4f7",
}

STATUS_LABEL: dict[str, str] = {
    "eye": "Naked eye",
    "phone": "Phone camera",
    "dslr": "DSLR/Mirrorless",
    "cloudy": "Cloudy",
    "nothing-eye": "Nothing (naked eye)",
    "nothing-phone": "Nothing (phone camera)",
    "nothing-dslr": "Nothing (DSLR/Mirrorless)",
}

SIGHTING_VISIBLE_STATUSES = {"eye", "phone", "dslr"}


# --- CMEs --------------------------------------------------------------


def _predicted_arrival_time(cme: dict[str, Any]) -> str | None:
    """Pull the estimated shock arrival from a linked GST event, if any."""
    for event in cme.get("linkedEvents") or []:
        activity_id = event.get("activityID") or ""
        if "-GST" not in activity_id:
            continue
        try:
            stamp = activity_id[:13]
            parsed = datetime(
                int(stamp[0:4]),
                int(stamp[4:6]),
                int(stamp[6:8]),
                int(stamp[9:11]),
                int(stamp[11:13]),
                tzinfo=timezone.utc,
            )
            return parsed.isoformat()
        except (ValueError, IndexError):
            return None
    return None


def process_cme_data(raw: Any, max_items: int = 20) -> list[dict[str, Any]]:
    """NASA DONKI CME analyses -> the same shape the app's CME list uses."""
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for cme in raw:
        if not isinstance(cme, dict):
            continue
        analyses = cme.get("cmeAnalyses") or []
        if not analyses:
            continue
        analysis = next((a for a in analyses if a.get("isMostAccurate")), analyses[0])
        speed = analysis.get("speed")
        longitude = analysis.get("longitude")
        latitude = analysis.get("latitude")
        if speed is None or longitude is None or latitude is None:
            continue
        try:
            longitude = float(longitude)
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "id": cme.get("activityID"),
                "start_time": cme.get("startTime"),
                "speed_km_s": speed,
                "longitude": longitude,
                "latitude": latitude,
                "is_earth_directed": abs(longitude) < 45,
                "note": cme.get("note") or "No additional details.",
                "predicted_arrival_time": _predicted_arrival_time(cme),
                "link": cme.get("link"),
                "instruments": ", ".join(
                    inst.get("displayName", "")
                    for inst in (cme.get("instruments") or [])
                )
                or "N/A",
                "source_location": cme.get("sourceLocation") or "N/A",
                "half_angle": analysis.get("halfAngle") or 30,
            }
        )

    out.sort(key=lambda c: c["start_time"] or "", reverse=True)
    return out[:max_items]


# --- Flares --------------------------------------------------------------


def process_flare_data(raw: Any, max_items: int = 20) -> list[dict[str, Any]]:
    """NASA DONKI flare events, newest peak first."""
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for flare in raw:
        if not isinstance(flare, dict):
            continue
        out.append(
            {
                "id": flare.get("flrID"),
                "start_time": flare.get("startTime"),
                "peak_time": flare.get("peakTime"),
                "end_time": flare.get("endTime"),
                "class_type": flare.get("classType"),
                "source_location": flare.get("sourceLocation") or "N/A",
                "active_region": flare.get("activeRegionNum"),
                "link": flare.get("link"),
            }
        )

    out.sort(key=lambda f: f["peak_time"] or "", reverse=True)
    return out[:max_items]


# --- X-ray flux ------------------------------------------------------------


def classify_xray(flux: float | None) -> str | None:
    """Convert a long-band W/m^2 flux into the standard A/B/C/M/X class."""
    if flux is None or flux <= 0 or not math.isfinite(flux):
        return None
    if flux < 1e-7:
        letter, base = "A", 1e-8
    elif flux < 1e-6:
        letter, base = "B", 1e-7
    elif flux < 1e-5:
        letter, base = "C", 1e-6
    elif flux < 1e-4:
        letter, base = "M", 1e-5
    else:
        letter, base = "X", 1e-4
    magnitude = flux / base
    return f"{letter}{magnitude:.1f}"


def process_xray(raw: Any) -> dict[str, Any]:
    """Latest short/long band X-ray flux and derived flare class."""
    out: dict[str, Any] = {
        "xray_flux_short": None,
        "xray_flux_long": None,
        "xray_class": None,
        "xray_time": None,
    }
    if not isinstance(raw, list):
        return out

    latest_short: dict[str, Any] | None = None
    latest_long: dict[str, Any] | None = None
    for row in raw:
        if not isinstance(row, dict):
            continue
        energy = str(row.get("energy") or "")
        if energy.startswith("0.05"):
            if latest_short is None or (row.get("time_tag") or "") > (
                latest_short.get("time_tag") or ""
            ):
                latest_short = row
        elif energy.startswith("0.1"):
            if latest_long is None or (row.get("time_tag") or "") > (
                latest_long.get("time_tag") or ""
            ):
                latest_long = row

    if latest_short is not None:
        try:
            out["xray_flux_short"] = float(latest_short.get("flux"))
        except (TypeError, ValueError):
            pass
    if latest_long is not None:
        try:
            out["xray_flux_long"] = float(latest_long.get("flux"))
        except (TypeError, ValueError):
            pass
        out["xray_time"] = latest_long.get("time_tag")

    out["xray_class"] = classify_xray(out["xray_flux_long"])
    return out


# --- Proton / energetic particle flux --------------------------------------


def process_proton_source(raw: Any) -> dict[str, Any] | None:
    """Latest reading from one /epam/raw?source=... feed."""
    if not isinstance(raw, dict) or not raw.get("ok", True):
        return None
    data = raw.get("data")
    if not isinstance(data, list) or not data:
        return None
    latest = data[-1]
    if not isinstance(latest, dict):
        return None

    channels = {key: latest.get(key) for key, _ in PROTON_CHANNELS}
    # p5 (310-580 keV) is a representative mid-energy channel for the
    # headline state; the full spectrum is in the attributes.
    return {
        "time_tag": latest.get("time_tag"),
        "value": channels.get("p5"),
        "channels": channels,
    }


# --- Aurora sightings ("reportings") ---------------------------------------


def _nz_tz():
    return dt_util.get_time_zone("Pacific/Auckland")


def nz_midday_cutoff_utc(now_utc: datetime | None = None) -> datetime:
    """The most recent local-NZ midday (12:00), returned as a UTC datetime.

    Reportings are for "tonight", so - like the live site - the list resets
    at midday NZ time: before local noon it still shows last night's
    reports, from local noon it starts empty again.
    """
    now_utc = now_utc or dt_util.utcnow()
    tz = _nz_tz()
    if tz is None:
        # Fallback: NZ has no DST-free simple offset, but +12/+13 covers
        # "midday" close enough that reportings still roll over daily.
        now_nz = now_utc + timedelta(hours=13)
        cutoff_nz = datetime.combine(now_nz.date(), time(12, 0), tzinfo=timezone.utc)
        if now_nz < cutoff_nz:
            cutoff_nz -= timedelta(days=1)
        return cutoff_nz - timedelta(hours=13)

    now_nz = now_utc.astimezone(tz)
    cutoff_nz = now_nz.replace(hour=12, minute=0, second=0, microsecond=0)
    if now_nz < cutoff_nz:
        cutoff_nz -= timedelta(days=1)
    return cutoff_nz.astimezone(timezone.utc)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def process_sightings(
    raw: Any,
    user_lat: float | None,
    user_lon: float | None,
    now_utc: datetime | None = None,
    max_items: int = 200,
) -> list[dict[str, Any]]:
    """Today's aurora sightings, newest first, with distance from the user.

    Filters out anything reported before the last NZ midday, matching the
    live site's daily reset, and (when a location is known) adds both a
    great-circle distance and a pure latitude ("how far north/south, i.e.
    how much closer to the pole") delta so automations can key off either.
    """
    if not isinstance(raw, list):
        return []

    cutoff = nz_midday_cutoff_utc(now_utc)
    cutoff_ms = cutoff.timestamp() * 1000

    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        timestamp = item.get("timestamp")
        lat = item.get("lat")
        lng = item.get("lng")
        status = item.get("status")
        if timestamp is None or lat is None or lng is None or status is None:
            continue
        try:
            timestamp = float(timestamp)
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            continue
        if timestamp < cutoff_ms:
            continue

        entry: dict[str, Any] = {
            "id": item.get("key") or f"{timestamp}:{item.get('name', '')}",
            "name": item.get("name") or "Anonymous",
            "status": status,
            "status_label": STATUS_LABEL.get(status, status),
            "emoji": STATUS_EMOJI.get(status, "❓"),
            "is_visible_sighting": status in SIGHTING_VISIBLE_STATUSES,
            "latitude": lat,
            "longitude": lng,
            "timestamp": timestamp,
            "reported_at": dt_util.utc_from_timestamp(timestamp / 1000).isoformat(),
        }

        if user_lat is not None and user_lon is not None:
            entry["distance_km"] = round(
                haversine_km(user_lat, user_lon, lat, lng), 1
            )
            entry["latitude_delta_deg"] = round(abs(lat - user_lat), 2)
            entry["latitude_delta_km"] = round(abs(lat - user_lat) * 111.0, 1)

        out.append(entry)

    out.sort(key=lambda s: s["timestamp"], reverse=True)
    return out[:max_items]
