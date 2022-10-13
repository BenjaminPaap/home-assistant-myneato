from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import MYNEATO_ROBOTS

from .lib.pyneato import (
    Account
)

_LOGGER = logging.getLogger(__name__)

class MyNeatoHub:
    def __init__(self, hass: HomeAssistant, account: Account):
        self._hass = hass
        self.account: Account = account

    async def update_robots(self):
        await self._hass.async_add_executor_job(
            self.account.refresh_robots,
        )

        _LOGGER.warning("Robots found %d" % len(self.account.robots))

    async def update_floorplans(self):
        await self._hass.async_add_executor_job(
            self.account.refresh_floorplans,
        )

        for floorplan in self.account.floorplans:
            await self._hass.async_add_executor_job(
                floorplan.refresh_tracks,
            )

        _LOGGER.warning("Floorplans found %d" % len(self.account.floorplans))

    async def async_update_entry_unique_id(self, entry: ConfigEntry):
        """Update entry for unique_id."""

        await self._hass.async_add_executor_job(self.account.get_userdata)
        unique_id: str = self.account.userdata["id"]

        if entry.unique_id == unique_id:
            return unique_id

        _LOGGER.debug("Updating user unique_id for previous config entry")
        self._hass.config_entries.async_update_entry(entry, unique_id=unique_id)
        return unique_id
