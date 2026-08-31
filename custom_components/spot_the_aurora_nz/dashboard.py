"""A dedicated Aurora dashboard, registered as its own sidebar panel.

Built from the entities this integration creates, so it works out of the box
with no YAML from the user. Can be turned off in the integration options.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import CME_VISUALIZATION_URL, DOMAIN, SOLAR_DASHBOARD_URL, SUVI_195_URL

_LOGGER = logging.getLogger(__name__)

PANEL_URL = "aurora"
PANEL_TITLE = "Aurora"
PANEL_ICON = "mdi:weather-night"


def _entity(hass: HomeAssistant, suffix: str) -> str | None:
    """Find one of our sensors by what it is, not by a guessed entity_id."""
    for state in hass.states.async_all("sensor"):
        if state.entity_id.endswith(suffix):
            return state.entity_id
    return None


def build_dashboard_config(hass: HomeAssistant) -> dict:
    """Assemble the Lovelace config from whichever entities exist."""
    e = lambda s: _entity(hass, s)  # noqa: E731

    vis_now = e("visibility_now")
    vis_15 = e("visibility_15_minutes")
    vis_30 = e("visibility_30_minutes")
    vis_60 = e("visibility_1_hour")
    vis_120 = e("visibility_2_hours")

    score = e("aurora_score")
    substorm = e("substorm_score")
    spot = e("spot_the_aurora_score")
    level = e("substorm_level")
    trend = e("substorm_trend")

    bz = e("imf_bz")
    bt = e("imf_bt")
    bz30 = e("imf_bz_30m_average")
    by = e("imf_by_30m_average")
    speed = e("solar_wind_speed")
    density = e("solar_wind_density")
    pressure = e("dynamic_pressure")
    newell = e("newell_coupling")
    southward = e("southward_minutes_30m")
    power = e("hemispheric_power")
    moon = e("moon_illumination")

    cme_count = e("cme_count")
    flare_count = e("solar_flare_count")
    xray = e("x_ray_flux_long_band")
    proton_solar1 = e("proton_flux_solar_1")
    proton_ace = e("proton_flux_ace")
    proton_imap = e("proton_flux_imap")
    sightings_count = e("aurora_sightings_today")
    closest_distance = e("closest_sighting_distance")
    closest_lat_delta = e("closest_sighting_latitude_difference")

    def rows(*pairs) -> list[dict]:
        return [
            {"entity": eid, "name": name}
            for eid, name in pairs
            if eid is not None
        ]

    def ids(*entities) -> list[str]:
        return [x for x in entities if x is not None]

    cards: list[dict] = [
        {
            "type": "custom:spot-the-aurora-card",
            "title": "Spot The Aurora",
            "height": "440px",
        }
    ]

    # --- 3 day outlook ------------------------------------------------------
    if e("kp_forecast"):
        cards.append(
            {
                "type": "custom:spot-the-aurora-forecast-card",
                "title": "3-day aurora forecast",
                "subtitle": (
                    "What the southern sky may look like over the next 72 hours"
                ),
            }
        )

    # --- Tonight at a glance ------------------------------------------------
    tonight = rows(
        (vis_now, "Now"),
        (vis_15, "15 minutes"),
        (vis_30, "30 minutes"),
        (vis_60, "1 hour"),
        (vis_120, "2 hours"),
    )
    if tonight:
        cards.append(
            {
                "type": "entities",
                "title": "Tonight",
                "show_header_toggle": False,
                "entities": tonight,
            }
        )

    # --- Activity -----------------------------------------------------------
    activity = rows(
        (level, "Substorm level"),
        (trend, "Trend"),
        (e("forecast_confidence"), "Confidence"),
        (score, "Aurora score"),
        (substorm, "Substorm score"),
        (spot, "Spot The Aurora score"),
        (e("kp_forecast"), "Peak Kp next 72h"),
    )
    if activity:
        cards.append(
            {
                "type": "entities",
                "title": "Activity",
                "show_header_toggle": False,
                "entities": activity,
            }
        )

    # --- Solar wind ---------------------------------------------------------
    glance = rows(
        (bz, "Bz"),
        (bt, "Bt"),
        (speed, "Speed"),
        (density, "Density"),
        (pressure, "Pressure"),
        (power, "Hemi power"),
    )
    if glance:
        cards.append(
            {
                "type": "glance",
                "title": "Solar wind",
                "columns": 3,
                "entities": glance,
            }
        )

    coupling = rows(
        (newell, "Newell"),
        (southward, "Southward 30m"),
        (moon, "Moon"),
    )
    if coupling:
        cards.append(
            {
                "type": "glance",
                "title": "Coupling & sky",
                "columns": 3,
                "entities": coupling,
            }
        )

    # --- X-ray & proton flux -------------------------------------------------
    xray_glance = rows(
        (xray, "X-ray (long)"),
        (proton_solar1, "Protons SOLAR-1"),
        (proton_ace, "Protons ACE"),
        (proton_imap, "Protons IMAP"),
        (cme_count, "CMEs tracked"),
        (flare_count, "Flares tracked"),
    )
    if xray_glance:
        cards.append(
            {
                "type": "glance",
                "title": "X-ray flux & proton flux",
                "columns": 3,
                "entities": xray_glance,
            }
        )

    # --- Map, with every current reporting on it ------------------------------
    cards.append(
        {
            "type": "map",
            "title": "Reportings map",
            "geo_location_sources": [DOMAIN],
            "default_zoom": 5,
            "entities": [],
        }
    )

    # --- Reportings list -------------------------------------------------------
    if sightings_count:
        cards.append(
            {
                "type": "markdown",
                "title": "Aurora reportings today",
                "content": (
                    "{% set sightings = state_attr('"
                    + sightings_count
                    + "', 'sightings') or [] %}"
                    "{% if sightings %}"
                    "{% for s in sightings[:15] %}"
                    "**{{ s.emoji }} {{ s.name }}** — {{ s.status_label }}"
                    "{% if s.distance_km is not none %} · {{ s.distance_km }} km away"
                    "{% endif %} · "
                    "{{ as_timestamp(s.reported_at) | timestamp_custom('%-I:%M %p') }}\n\n"
                    "{% endfor %}"
                    "{% else %}"
                    "No reportings since midday - be the first tonight!"
                    "{% endif %}"
                ),
            }
        )

    # --- Closest reporting, for at-a-glance proximity ---------------------------
    closest = rows(
        (closest_distance, "Distance"),
        (closest_lat_delta, "Latitude difference"),
    )
    if closest:
        cards.append(
            {
                "type": "glance",
                "title": "Closest reporting",
                "columns": 2,
                "entities": closest,
            }
        )

    # --- CME list ---------------------------------------------------------------
    if cme_count:
        cards.append(
            {
                "type": "markdown",
                "title": "Recent CMEs",
                "content": (
                    "{% set cmes = state_attr('"
                    + cme_count
                    + "', 'cmes') or [] %}"
                    "{% if cmes %}"
                    "{% for c in cmes[:10] %}"
                    "**{{ as_timestamp(c.start_time) | timestamp_custom('%-d %b, %-I:%M %p') "
                    "if c.start_time else 'Unknown time' }}** — "
                    "{{ c.speed_km_s | round(0) }} km/s"
                    "{% if c.is_earth_directed %} · 🌍 Earth-directed{% endif %}"
                    "{% if c.predicted_arrival_time %} · arrival ~"
                    "{{ as_timestamp(c.predicted_arrival_time) | timestamp_custom('%-d %b, %-I:%M %p') }}"
                    "{% endif %}\n\n"
                    "{% endfor %}"
                    "{% else %}"
                    "No recent CMEs from NASA DONKI."
                    "{% endif %}"
                ),
            }
        )

    # --- Flare list ---------------------------------------------------------------
    if flare_count:
        cards.append(
            {
                "type": "markdown",
                "title": "Recent solar flares",
                "content": (
                    "{% set flares = state_attr('"
                    + flare_count
                    + "', 'flares') or [] %}"
                    "{% if flares %}"
                    "{% for f in flares[:10] %}"
                    "**{{ f.class_type or '?' }}** — {{ f.source_location or 'unknown region' }}"
                    "{% if f.peak_time %} · peak "
                    "{{ as_timestamp(f.peak_time) | timestamp_custom('%-d %b, %-I:%M %p') }}"
                    "{% endif %}\n\n"
                    "{% endfor %}"
                    "{% else %}"
                    "No recent flares from NASA DONKI."
                    "{% endif %}"
                ),
            }
        )

    # --- Full 3D CME & coronal hole visualization (the actual web app) ---------
    # The 3D propagation model and coronal hole detection aren't practical to
    # rebuild as a Lovelace card, and the site isn't built to be framed - so
    # link straight to the live pages instead of embedding them.
    cards.append(
        {
            "type": "markdown",
            "content": (
                "### \U0001f30c Full 3D CME & coronal hole visualization\n\n"
                "This dashboard shows the *data*. For the real interactive 3D "
                f"model - CME propagation, coronal holes and all - open the "
                f"live app: **[CME Visualization]({CME_VISUALIZATION_URL})** · "
                f"**[Solar Activity Dashboard]({SOLAR_DASHBOARD_URL})**"
            ),
        }
    )

    # --- Solar imagery (best effort - static NASA image feeds) -----------------
    cards.append(
        {
            "type": "grid",
            "title": "Solar imagery",
            "columns": 2,
            "square": False,
            "cards": [
                {
                    "type": "picture",
                    "image": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0193.jpg",
                    "tap_action": {"action": "url", "url_path": "https://sdo.gsfc.nasa.gov/data/"},
                },
                {
                    "type": "picture",
                    "image": "https://soho.nascom.nasa.gov/data/realtime/c3diff/1024/latest.jpg",
                    "tap_action": {
                        "action": "url",
                        "url_path": "https://soho.nascom.nasa.gov/data/realtime/",
                    },
                },
                {
                    "type": "picture",
                    "image": SUVI_195_URL,
                    "tap_action": {
                        "action": "url",
                        "url_path": SOLAR_DASHBOARD_URL,
                    },
                },
            ],
        }
    )
    cards.append(
        {
            "type": "markdown",
            "content": (
                "SDO AIA 193Å, SOHO LASCO C3 running-difference coronagraph, "
                "and GOES SUVI 195Å (coronal holes show as dark patches, "
                "usually near the poles). These load straight from NASA and "
                "only refresh when the dashboard reloads."
            ),
        }
    )

    # --- History ------------------------------------------------------------
    if imf := ids(bt, bz, bz30, by):
        cards.append(
            {
                "type": "history-graph",
                "title": "IMF - Bt & Bz (nT)",
                "hours_to_show": 12,
                "entities": imf,
            }
        )

    if plasma := ids(speed, density):
        cards.append(
            {
                "type": "history-graph",
                "title": "Solar wind - speed & density",
                "hours_to_show": 12,
                "entities": plasma,
            }
        )

    if pres := ids(pressure, newell):
        cards.append(
            {
                "type": "history-graph",
                "title": "Pressure & coupling",
                "hours_to_show": 12,
                "entities": pres,
            }
        )

    if scores := ids(score, substorm, spot):
        cards.append(
            {
                "type": "history-graph",
                "title": "Activity scores",
                "hours_to_show": 24,
                "entities": scores,
            }
        )

    if tiers := ids(vis_now, vis_30, vis_120):
        cards.append(
            {
                "type": "logbook",
                "title": "Visibility changes",
                "hours_to_show": 24,
                "entities": tiers,
            }
        )

    cards.append(
        {
            "type": "markdown",
            "content": (
                "Kp forecast, X-ray flux and CME/flare catalog from "
                "[NOAA SWPC](https://www.swpc.noaa.gov/) and "
                "[NASA DONKI](https://ccmc.gsfc.nasa.gov/tools/DONKI/). "
                "Proton flux from the SOLAR-1, ACE and IMAP spacecraft. "
                "Solar wind, aurora reportings and forecast algorithm via "
                "[Spot The Aurora](https://www.spottheaurora.co.nz), by "
                "[TNR Protography](https://www.tnrprotography.co.nz)."
            ),
        }
    )

    return {
        "views": [
            {
                "title": PANEL_TITLE,
                "path": "aurora",
                "icon": PANEL_ICON,
                "cards": cards,
            }
        ]
    }


async def async_register_dashboard(hass: HomeAssistant) -> None:
    """Add the Aurora dashboard to the sidebar."""
    if hass.data.get(f"{DOMAIN}_panel_registered"):
        return

    try:
        from homeassistant.components import frontend

        frontend.async_register_built_in_panel(
            hass,
            component_name="lovelace",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            frontend_url_path=PANEL_URL,
            config={
                "mode": "storage",
                "views": build_dashboard_config(hass)["views"],
            },
            require_admin=False,
            update=True,
        )
        hass.data[f"{DOMAIN}_panel_registered"] = True
        _LOGGER.info("Registered Aurora dashboard at /%s", PANEL_URL)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Could not register the Aurora dashboard: %s. "
            "You can still build one by hand - see example-dashboard.yaml",
            err,
        )


async def async_remove_dashboard(hass: HomeAssistant) -> None:
    """Take the dashboard back out of the sidebar."""
    if not hass.data.get(f"{DOMAIN}_panel_registered"):
        return
    try:
        from homeassistant.components import frontend

        frontend.async_remove_panel(hass, PANEL_URL)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not remove panel: %s", err)
    hass.data.pop(f"{DOMAIN}_panel_registered", None)
