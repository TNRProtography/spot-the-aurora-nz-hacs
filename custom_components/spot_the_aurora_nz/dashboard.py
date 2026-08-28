"""A dedicated Aurora dashboard, registered as its own sidebar panel.

Built from the entities this integration creates, so it works out of the box
with no YAML from the user. Can be turned off in the integration options.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import DOMAIN

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

    visibility_rows = rows(
        (vis_now, "Now"),
        (vis_15, "15 minutes"),
        (vis_30, "30 minutes"),
        (vis_60, "1 hour"),
        (vis_120, "2 hours"),
    )
    status_rows = rows(
        (level, "Substorm level"),
        (trend, "Trend"),
        (score, "Aurora score"),
        (substorm, "Substorm score"),
        (spot, "Spot The Aurora score"),
    )
    if visibility_rows or status_rows:
        entities: list = list(visibility_rows)
        if visibility_rows and status_rows:
            entities.append({"type": "divider"})
        entities.extend(status_rows)
        cards.append(
            {
                "type": "entities",
                "title": "Visibility forecast",
                "show_header_toggle": False,
                "entities": entities,
            }
        )

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
                "title": "Coupling",
                "columns": 3,
                "entities": coupling,
            }
        )

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

    if scores := ids(score, substorm, spot):
        cards.append(
            {
                "type": "history-graph",
                "title": "Activity scores",
                "hours_to_show": 24,
                "entities": scores,
            }
        )

    cards.append(
        {
            "type": "markdown",
            "content": (
                "Data from NOAA SWPC and NASA via Spot The Aurora. "
                "Forecast algorithm by "
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
