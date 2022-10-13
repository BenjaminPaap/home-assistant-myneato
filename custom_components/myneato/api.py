from __future__ import annotations

from asyncio import run_coroutine_threadsafe
from typing import Any

import logging
from .lib.pyneato import (
    Neato,
    OrbitalPasswordSession,
)

from homeassistant import config_entries, core
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

class ConfigEntrySession(OrbitalPasswordSession):
    def __init__(
        self,
        hass: core.HomeAssistant,
        entry: config_entries.ConfigEntry,
    ) -> None:
        super().__init__(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], entry.data[CONF_TOKEN], vendor=Neato())
        self.is_active = entry.data[CONF_TOKEN] != None

    async def async_ensure_token_valid(self):
        return True
