"""Config and options flow for Spot The Aurora NZ."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CREATE_DASHBOARD,
    CONF_LOCATION,
    CONF_LOCATION_MODE,
    CONF_SCAN_INTERVAL,
    CONF_TRACKED_ENTITY,
    DOMAIN,
    MODE_ENTITY,
    MODE_HOME,
    MODE_PIN,
    NAME,
)

DASHBOARD_SELECTOR = selector.BooleanSelector()

SCAN_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=30, max=900, step=30, unit_of_measurement="s", mode="slider"
    )
)

ENTITY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["device_tracker", "person", "zone"])
)


def _pin_schema(defaults: dict[str, Any], lat: float, lon: float) -> vol.Schema:
    location = defaults.get(CONF_LOCATION) or {
        "latitude": lat,
        "longitude": lon,
    }
    return vol.Schema(
        {
            vol.Required(CONF_LOCATION, default=location): selector.LocationSelector(
                selector.LocationSelectorConfig(radius=False)
            ),
            vol.Optional(
                CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, 60)
            ): SCAN_SELECTOR,
            vol.Optional(
                CONF_CREATE_DASHBOARD,
                default=defaults.get(CONF_CREATE_DASHBOARD, True),
            ): DASHBOARD_SELECTOR,
        }
    )


def _entity_schema(defaults: dict[str, Any]) -> vol.Schema:
    schema: dict[Any, Any] = {}
    tracked = defaults.get(CONF_TRACKED_ENTITY)
    if tracked:
        schema[vol.Required(CONF_TRACKED_ENTITY, default=tracked)] = ENTITY_SELECTOR
    else:
        schema[vol.Required(CONF_TRACKED_ENTITY)] = ENTITY_SELECTOR
    schema[
        vol.Optional(CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, 60))
    ] = SCAN_SELECTOR
    schema[
        vol.Optional(
            CONF_CREATE_DASHBOARD, default=defaults.get(CONF_CREATE_DASHBOARD, True)
        )
    ] = DASHBOARD_SELECTOR
    return vol.Schema(schema)


def _home_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, 60)
            ): SCAN_SELECTOR,
            vol.Optional(
                CONF_CREATE_DASHBOARD,
                default=defaults.get(CONF_CREATE_DASHBOARD, True),
            ): DASHBOARD_SELECTOR,
        }
    )


class AuroraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup: choose how the forecast should know where you are."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_show_menu(
            step_id="user",
            menu_options=[MODE_HOME, MODE_ENTITY, MODE_PIN],
        )

    async def async_step_home(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={CONF_LOCATION_MODE: MODE_HOME, **user_input},
            )
        return self.async_show_form(
            step_id=MODE_HOME,
            data_schema=_home_schema({}),
            description_placeholders={
                "latitude": f"{self.hass.config.latitude:.4f}",
                "longitude": f"{self.hass.config.longitude:.4f}",
            },
        )

    async def async_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input[CONF_TRACKED_ENTITY]
            state = self.hass.states.get(entity_id)
            if state is None or (
                state.attributes.get("latitude") is None
                and state.attributes.get("longitude") is None
            ):
                errors[CONF_TRACKED_ENTITY] = "no_location"
            else:
                return self.async_create_entry(
                    title=NAME,
                    data={CONF_LOCATION_MODE: MODE_ENTITY, **user_input},
                )
        return self.async_show_form(
            step_id=MODE_ENTITY,
            data_schema=_entity_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={CONF_LOCATION_MODE: MODE_PIN, **user_input},
            )
        return self.async_show_form(
            step_id=MODE_PIN,
            data_schema=_pin_schema(
                {}, self.hass.config.latitude, self.hass.config.longitude
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return AuroraOptionsFlow()


class AuroraOptionsFlow(OptionsFlow):
    """Change location or polling interval after setup."""

    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[MODE_HOME, MODE_ENTITY, MODE_PIN],
        )

    async def async_step_home(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="", data={CONF_LOCATION_MODE: MODE_HOME, **user_input}
            )
        return self.async_show_form(
            step_id=MODE_HOME,
            data_schema=_home_schema(self._current()),
            description_placeholders={
                "latitude": f"{self.hass.config.latitude:.4f}",
                "longitude": f"{self.hass.config.longitude:.4f}",
            },
        )

    async def async_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            state = self.hass.states.get(user_input[CONF_TRACKED_ENTITY])
            if state is None or (
                state.attributes.get("latitude") is None
                and state.attributes.get("longitude") is None
            ):
                errors[CONF_TRACKED_ENTITY] = "no_location"
            else:
                return self.async_create_entry(
                    title="", data={CONF_LOCATION_MODE: MODE_ENTITY, **user_input}
                )
        return self.async_show_form(
            step_id=MODE_ENTITY,
            data_schema=_entity_schema(user_input or self._current()),
            errors=errors,
        )

    async def async_step_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="", data={CONF_LOCATION_MODE: MODE_PIN, **user_input}
            )
        return self.async_show_form(
            step_id=MODE_PIN,
            data_schema=_pin_schema(
                self._current(),
                self.hass.config.latitude,
                self.hass.config.longitude,
            ),
        )
