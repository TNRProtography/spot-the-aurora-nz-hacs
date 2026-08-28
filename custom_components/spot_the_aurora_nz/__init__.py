"""Spot The Aurora NZ - aurora forecast for Kiwis."""

from __future__ import annotations

import logging
import os
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CARD_FILENAME,
    CARD_URL,
    CONF_CREATE_DASHBOARD,
    FORECAST_CARD_URL,
    CONF_LOCATION_MODE,
    CONF_SCAN_INTERVAL,
    CONF_TRACKED_ENTITY,
    DOMAIN,
    MODE_ENTITY,
)
from .coordinator import AuroraCoordinator
from .dashboard import async_register_dashboard, async_remove_dashboard

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def _register_card(hass: HomeAssistant) -> None:
    """Serve the Lovelace card and load it, so the user needs no resource entry."""
    if hass.data.get(f"{DOMAIN}_card_registered"):
        return

    www_path = os.path.join(os.path.dirname(__file__), "www")
    card_path = os.path.join(www_path, CARD_FILENAME)
    if not os.path.exists(card_path):
        _LOGGER.warning("Card file missing at %s", card_path)
        return

    # Serve the whole folder so the logo and any future assets resolve too.
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"/{DOMAIN}", www_path, True)]
        )
    except ImportError:
        # Older cores without StaticPathConfig
        hass.http.register_static_path(f"/{DOMAIN}", www_path, True)

    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, f"{CARD_URL}?v=1.3.0")
        add_extra_js_url(hass, f"{FORECAST_CARD_URL}?v=1.3.0")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not auto-register the card: %s", err)

    hass.data[f"{DOMAIN}_card_registered"] = True
    _LOGGER.info("Registered Aurora card at %s", CARD_URL)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    await _register_card(hass)

    opts = {**entry.data, **entry.options}
    interval = timedelta(seconds=int(opts.get(CONF_SCAN_INTERVAL, 60)))

    coordinator = AuroraCoordinator(hass, opts, interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # When tracking a device, recompute as soon as it reports a new position
    # rather than waiting for the next poll.
    if opts.get(CONF_LOCATION_MODE) == MODE_ENTITY:
        tracked = opts.get(CONF_TRACKED_ENTITY)
        if tracked:

            async def _tracker_moved(event) -> None:
                new = event.data.get("new_state")
                old = event.data.get("old_state")
                if new is None:
                    return
                if old is not None and (
                    old.attributes.get("latitude") == new.attributes.get("latitude")
                    and old.attributes.get("longitude")
                    == new.attributes.get("longitude")
                ):
                    return
                await coordinator.async_request_refresh()

            entry.async_on_unload(
                async_track_state_change_event(hass, [tracked], _tracker_moved)
            )

    # The dashboard is built from live entities, so register it only once
    # they exist. Failure here never breaks the integration.
    if opts.get(CONF_CREATE_DASHBOARD, True):
        await async_register_dashboard(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await async_remove_dashboard(hass)
    return unloaded
