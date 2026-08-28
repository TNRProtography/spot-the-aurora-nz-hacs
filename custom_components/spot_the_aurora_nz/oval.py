"""Auroral oval and visibility physics.

Ported from Spot The Aurora's utils/ovalPhysics.ts,
components/AuroraSightings.tsx and components/VisibilityForecastPanel.tsx
so this integration, the card and the app all agree.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

D2R = math.pi / 180.0
R2D = 180.0 / math.pi

# IGRF-13 north magnetic dipole pole (geographic)
POLE_LAT_RAD = 80.65 * D2R
POLE_LON_RAD = -72.68 * D2R

QUIET_BOUNDARY = -65.5
QUIET_HALFWIDTH = 3.5

PDYN_NOMINAL_NPA = 2.0
PDYN_DEG_PER_DOUBLING = 0.9
PDYN_SHIFT_MIN = -1.0
PDYN_SHIFT_MAX = 3.0


def geo_to_gmag_lat(lat_deg: float, lon_deg: float) -> float:
    """Geographic latitude -> geomagnetic latitude (dipole approximation)."""
    phi = lat_deg * D2R
    lam = lon_deg * D2R
    s = math.sin(phi) * math.sin(POLE_LAT_RAD) + math.cos(phi) * math.cos(
        POLE_LAT_RAD
    ) * math.cos(lam - POLE_LON_RAD)
    return math.asin(max(-1.0, min(1.0, s))) * R2D


def gmag_to_geo_lat(gmag_lat: float, lon_deg: float) -> float:
    """Numerical inversion of geo_to_gmag_lat by bisection."""
    lo, hi = -90.0, 90.0
    for _ in range(48):
        mid = (lo + hi) / 2.0
        if geo_to_gmag_lat(mid, lon_deg) < gmag_lat:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _rm_beta(when: datetime) -> float:
    """Hapgood (1992) angles for the GSM->GSEQ By projection."""
    mjd = when.timestamp() / 86400.0 + 40587.0
    t0 = (mjd - 51544.5) / 36525.0
    h = when.hour + when.minute / 60.0 + when.second / 3600.0

    m = (357.528 + 35999.050 * t0 + 0.04107 * h) * D2R
    lam_deg = 280.460 + 36000.772 * t0 + 0.04107 * h
    lambda_sun = (
        lam_deg + (1.915 - 0.0048 * t0) * math.sin(m) + 0.020 * math.sin(2 * m)
    ) * D2R
    eps = (23.439 - 0.013 * t0) * D2R
    theta = ((100.461 + 36000.770 * t0 + 15.04107 * h) % 360.0) * D2R

    phi, lam = 80.65 * D2R, -72.68 * D2R
    qg = [math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)]

    ct, st = math.cos(theta), math.sin(theta)
    qei = [ct * qg[0] - st * qg[1], st * qg[0] + ct * qg[1], qg[2]]

    ce, se = math.cos(eps), math.sin(eps)
    a = [qei[0], ce * qei[1] + se * qei[2], -se * qei[1] + ce * qei[2]]

    cl, sl = math.cos(lambda_sun), math.sin(lambda_sun)
    qgse = [cl * a[0] + sl * a[1], -sl * a[0] + cl * a[1], a[2]]

    psi = math.atan2(qgse[1], qgse[2]) * R2D
    i_s, omega = 7.25 * D2R, 75.76 * D2R
    delta = math.atan(math.tan(i_s) * math.sin(lambda_sun - omega)) * R2D
    return psi + delta


def russell_mcpherron_factor(
    when: datetime, by_gsm: float | None, bz_gsm: float | None
) -> float:
    """Seasonal coupling multiplier, capped to [0.90, 1.15]."""
    if by_gsm is None or not math.isfinite(by_gsm):
        return 1.0
    sin_b = math.sin(_rm_beta(when) * D2R)
    projection = by_gsm * sin_b
    bz_mag = abs(bz_gsm or 0.0)
    marginality = 1.0 / (1.0 + bz_mag / 5.0)
    raw = 1.0 - 0.03 * projection * marginality
    return min(1.15, max(0.90, raw))


def pressure_shift_degrees(pdyn_npa: float | None) -> float:
    """Equatorward shift in degrees from solar wind dynamic pressure."""
    if pdyn_npa is None or not math.isfinite(pdyn_npa) or pdyn_npa <= 0:
        return 0.0
    shift = PDYN_DEG_PER_DOUBLING * math.log2(
        max(pdyn_npa, 0.25) / PDYN_NOMINAL_NPA
    )
    return min(PDYN_SHIFT_MAX, max(PDYN_SHIFT_MIN, shift))


def compute_oval_boundary(
    newell_avg_60m: float | None = None,
    newell_avg_30m: float | None = None,
    pressure_npa: float | None = None,
    by: float | None = None,
    bz: float | None = None,
    bay_onset: bool = False,
    when: datetime | None = None,
) -> float:
    """Southern-hemisphere equatorward oval boundary, geomagnetic degrees."""
    when = when or datetime.now(timezone.utc)

    n60 = newell_avg_60m or 0.0
    n30 = newell_avg_30m or 0.0
    newell = max(n60, n30 * 0.85)
    newell *= russell_mcpherron_factor(when, by, bz)

    boundary = -(65.5 - newell / 1800.0)
    boundary += pressure_shift_degrees(pressure_npa)
    boundary = max(boundary, -76.0)
    boundary = min(boundary, -44.0)
    if bay_onset:
        boundary = min(boundary, -47.2)
    return boundary


def visibility_line(boundary: float, score: float) -> float:
    """Geomagnetic latitude of the visibility horizon."""
    vis_deg = 9.0 + (max(0.0, min(score, 100.0)) / 100.0) * 16.0
    return boundary + vis_deg


def location_adjusted_score(
    raw_score: float,
    user_lat: float | None,
    user_lon: float | None,
    boundary: float,
) -> float:
    """Reduce the score when the user sits north of the visibility line."""
    if user_lat is None or user_lon is None:
        return raw_score
    user_gmag = geo_to_gmag_lat(user_lat, user_lon)
    vis_horizon = visibility_line(boundary, raw_score)
    dist_from_vis = user_gmag - vis_horizon
    if dist_from_vis <= 0:
        return raw_score
    penalty = min(1.0, dist_from_vis / 2.0)
    return raw_score * (1.0 - penalty)


# --- Score projection (VisibilityForecastPanel.tsx) -------------------------

_TREND_MULT = {
    "Rapidly Increasing": 1.18,
    "Increasing": 1.08,
    "Decreasing": 0.88,
    "Rapidly Decreasing": 0.72,
}

# The app derives p30/p60 from a local L1 probability model that the
# substorm worker does not expose. These are level-based stand-ins.
_LEVEL_P = {
    "IMMINENT": (0.70, 0.70),
    "LIKELY": (0.40, 0.65),
    "WATCH": (0.0, 0.35),
}


def _status_from_level(level: str | None) -> str:
    up = (level or "").upper()
    if "ONSET" in up:
        return "ONSET"
    if "IMMINENT" in up:
        return "IMMINENT_30"
    if "LIKELY" in up:
        return "LIKELY_60"
    if "WATCH" in up:
        return "WATCH"
    return "QUIET"


def _boost_from_p(p: float, base: float) -> float:
    return base + p * (100.0 - base) * 0.75


def project_scores(
    score: float,
    level: str | None,
    trend: str | None,
    newell_now: float | None,
    newell_avg_30m: float | None,
    confidence: float | None,
) -> dict[str, float]:
    """15/30/60-minute projections from the substorm worker's own signals."""
    status = _status_from_level(level)

    trend_mult = _TREND_MULT.get(trend or "", 1.0)

    newell_accel = (
        newell_now is not None
        and newell_avg_30m is not None
        and newell_avg_30m > 0
        and newell_now > newell_avg_30m * 1.2
    )
    newell_boost = 1.08 if newell_accel else 1.0

    conf_mult = (
        0.7 + (confidence / 100.0) * 0.3
        if confidence is not None and confidence >= 0
        else 1.0
    )

    if status == "ONSET":
        s15, s30, s60 = score * 1.05, score * 0.90, score * 0.62
    elif status == "IMMINENT_30":
        p30, p60 = _LEVEL_P["IMMINENT"]
        s15 = _boost_from_p(p30, score)
        s30 = _boost_from_p(p30, score) * 1.05
        s60 = _boost_from_p(p60, score) * 0.78
    elif status == "LIKELY_60":
        p30, p60 = _LEVEL_P["LIKELY"]
        s15 = score * 1.08
        s30 = _boost_from_p(p30 * 0.65, score)
        s60 = _boost_from_p(p60, score)
    elif status == "WATCH":
        _, p60 = _LEVEL_P["WATCH"]
        s15 = score * 1.04
        s30 = score * 1.12
        s60 = _boost_from_p(p60 * 0.45, score)
    else:
        s15, s30, s60 = score * 0.94, score * 0.83, score * 0.68

    def apply(v: float) -> float:
        return max(0.0, min(100.0, v * trend_mult * newell_boost * conf_mult))

    return {
        "status": status,
        "score_15": apply(s15),
        "score_30": apply(s30),
        "score_60": apply(s60),
    }


# --- Visibility tiers (getVisibilityPhrase) ---------------------------------

TIER_EYE = "Eye"
TIER_PHONE = "Phone"
TIER_CAMERA = "Camera"
TIER_NOTHING = "Nothing"


def visibility_tier(score: float) -> str:
    """Nothing / Camera / Phone / Eye, using the app's thresholds."""
    if score >= 50:
        return TIER_EYE
    if score >= 35:
        return TIER_PHONE
    if score >= 20:
        return TIER_CAMERA
    return TIER_NOTHING


def tier_icon(tier: str) -> str:
    return {
        TIER_EYE: "mdi:eye",
        TIER_PHONE: "mdi:cellphone",
        TIER_CAMERA: "mdi:camera",
    }.get(tier, "mdi:sleep")


# --- Kp visibility threshold ----------------------------------------------
#
# The equatorward auroral boundary sits near 66.5 deg corrected geomagnetic
# latitude at Kp 0 and moves roughly 2 deg equatorward per Kp step. Aurora is
# visible on the horizon from about 9 deg equatorward of that boundary, which
# is the same allowance the oval code uses for its view line.
#
#     visible when  |gmag| >= 66.5 - 2*Kp - 9
#     so            Kp_threshold = (57.5 - |gmag|) / 2
#
# Christchurch (-46.8 gmag) lands at Kp 5.4, consistent with the Kp 5 rule of
# thumb aurora chasers use for the South Island.

KP_BOUNDARY_BASE = 66.5
KP_DEG_PER_STEP = 2.0
KP_HORIZON_DEG = 9.0


def kp_threshold_for_latitude(gmag_lat: float) -> float:
    """Lowest Kp at which aurora becomes visible from this geomagnetic lat."""
    return max(
        0.0,
        (KP_BOUNDARY_BASE - KP_HORIZON_DEG - abs(gmag_lat)) / KP_DEG_PER_STEP,
    )


def kp_boundary_gmag(kp: float) -> float:
    """Equatorward auroral boundary for a given Kp, in geomagnetic degrees."""
    return KP_BOUNDARY_BASE - KP_DEG_PER_STEP * max(0.0, kp)
