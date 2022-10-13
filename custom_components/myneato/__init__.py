"""A MyNeato vacuum robot integration"""
import logging
import sys
import os
import pathlib
import aiohttp

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform, CONF_TOKEN
from homeassistant.helpers.typing import ConfigType

from .lib.pyneato import Account

from .const import MYNEATO_DOMAIN, MYNEATO_LOGIN, MYNEATO_CONFIG, MYNEATO_ROBOTS, MYNEATO_FLOORPLANS
from .api import ConfigEntrySession
from .hub import MyNeatoHub

directory_path = os.getcwd()
sys.path.append("%spyneato"%(
    str(pathlib.Path(__file__).parent.absolute()) + os.sep + "lib" + os.sep + "pyneato"
))

print("%spyneato"%(
  str(pathlib.Path(__file__).parent.absolute()) + os.sep + "lib" + os.sep + "pyneato"
))
_LOGGER = logging.getLogger(__name__)

#Platform.SWITCH,
PLATFORMS = [Platform.VACUUM, Platform.SENSOR]

SCAN_INTERVAL = timedelta(minutes=1)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MyNeato component."""
    hass.data[MYNEATO_DOMAIN] = {}
    hass.data[MYNEATO_ROBOTS] = []
    hass.data[MYNEATO_FLOORPLANS] = []

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    if CONF_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed

    session = ConfigEntrySession(hass, entry)

    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as ex:
        _LOGGER.debug("API error: %s (%s)", ex.code, ex.message)
        if ex.code in (401, 403):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
        raise ConfigEntryNotReady from ex

    hass.data[MYNEATO_DOMAIN][entry.entry_id] = session
    hub = MyNeatoHub(hass, Account(session))

    await hub.async_update_entry_unique_id(entry)

    try:
        await hub.update_robots()
        await hub.update_floorplans()
    except NeatoException as ex:
        _LOGGER.debug("Failed to connect to MyNeato API")
        raise ConfigEntryNotReady from ex

    hass.data[MYNEATO_LOGIN] = hub
    hass.data[MYNEATO_ROBOTS] = hub.account.robots
    hass.data[MYNEATO_FLOORPLANS] = hub.account.floorplans

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[NEATO_DOMAIN].pop(entry.entry_id)

    return unload_ok
