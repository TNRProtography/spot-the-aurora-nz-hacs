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

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
FORECAST_SCAN_MULTIPLIER = 2  # composite score polled half as often

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
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"

ATTRIBUTION = "Data from NOAA SWPC and NASA via Spot The Aurora"
