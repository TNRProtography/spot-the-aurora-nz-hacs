"""Constants for Spot The Aurora NZ."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "spot_the_aurora_nz"
NAME = "Spot The Aurora NZ"

# Upstream endpoints (same ones the web app uses)
FORECAST_URL = "https://spottheaurora.thenamesrock.workers.dev/"
SUBSTORM_URL = (
    "https://aurora-index-sta.thenamesrock.workers.dev/api/substorm?resolution=5m"
)
RTSW_URL = "https://imap-solar-data-test.thenamesrock.workers.dev/rtsw/merged-24h"
KP_FORECAST_URL = (
    "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
)

# CME and solar flare catalog, proxied from NASA DONKI (same source the CME
# Modeler app uses).
DONKI_BASE = "https://nasa-donki-api.thenamesrock.workers.dev"
CME_URL = f"{DONKI_BASE}/CME"
FLARE_URL = f"{DONKI_BASE}/FLR"

# GOES primary X-ray flux (short 0.05-0.4nm / long 0.1-0.8nm bands).
XRAY_URL = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"

# Energetic-particle (proton/electron) feeds from three independent L1
# spacecraft, proxied by the same worker the app's EPAM panel uses.
EPAM_BASE = "https://epam.thenamesrock.workers.dev"
PROTON_SOURCES = ("solar1", "ace", "imap")

# Community aurora sightings ("reportings").
SIGHTINGS_URL = "https://aurora-sightings.thenamesrock.workers.dev/"
NZ_TIMEZONE = "Pacific/Auckland"

# The full web app - its 3D CME/coronal-hole visualization and solar
# activity dashboard aren't practical to rebuild as a Lovelace card, so the
# integration's dashboard links (and tries to embed) the live pages instead.
APP_BASE_URL = "https://www.spottheaurora.co.nz"
CME_VISUALIZATION_URL = f"{APP_BASE_URL}/cme-visualization"
SOLAR_DASHBOARD_URL = f"{APP_BASE_URL}/solar-dashboard"

# Raw NOAA SUVI 195A image - coronal holes are the dark patches, same source
# image the app's client-side coronal hole detector analyses.
SUVI_195_URL = "https://services.swpc.noaa.gov/images/animations/suvi/primary/195/latest.png"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
FORECAST_SCAN_MULTIPLIER = 2  # composite score polled half as often
SLOW_POLL_TICKS = 10  # CMEs/flares/x-ray/proton change slowly - poll rarely
SIGHTINGS_POLL_TICKS = 2  # sightings are near-real-time - poll every couple of minutes

CONF_LOCATION_MODE = "location_mode"
CONF_LOCATION = "location"
CONF_TRACKED_ENTITY = "tracked_entity"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CREATE_DASHBOARD = "create_dashboard"

MODE_HOME = "home"
MODE_ENTITY = "entity"
MODE_PIN = "pin"

# Frontend card
CARD_FILENAME = "spot-the-aurora-card.js"
FORECAST_CARD_FILENAME = "spot-the-aurora-forecast-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
FORECAST_CARD_URL = f"/{DOMAIN}/{FORECAST_CARD_FILENAME}"

ATTRIBUTION = "Data from NOAA SWPC and NASA via Spot The Aurora"
