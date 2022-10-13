"""Config flow for MyNeato."""
from __future__ import annotations

import logging

from asyncio import run_coroutine_threadsafe
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN

from .const import MYNEATO_DOMAIN
from pyneato import (
    OrbitalPasswordSession,
)

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Optional(CONF_PASSWORD): str
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        MYNEATO_DOMAIN: AUTH_SCHEMA
    },
    extra=vol.ALLOW_EXTRA,
)

class MyNeatoConfigFlow(config_entries.ConfigFlow, domain=MYNEATO_DOMAIN):
    """Example config flow."""
    def __init__(self):
        self.user_input = None

    def is_valid(self, user, password) -> bool:
        session = OrbitalPasswordSession(
            user,
            password
        )

        return session

    async def async_step_user(self, user_input: vol.Optional[Dict[str, Any]] = None):
        """Invoked when a user initiates a flow via the user interface."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                _LOGGER.debug(user_input)
                _LOGGER.warning("TEST")
                session = await self.hass.async_add_executor_job(
                    self.is_valid,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD]
                )
                _LOGGER.warning(session)
                _LOGGER.warning(session.is_active)

                if session.is_active:
                    user_input[CONF_TOKEN] = session.access_token
                    data = user_input
                else:
                    errors["base"] = "auth_error"
                    return self.async_show_form(
                        step_id="user", data_schema=AUTH_SCHEMA, errors=errors
                    )

                return self.async_create_entry(title="MyNeato", data=data)

            except ValueError:
                errors["base"] = "auth"

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )
