"""Support for loading picture from Neato."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyneato import (
    Robot,
    MyNeatoRobotException,
)
from urllib3.response import HTTPResponse

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    MYNEATO_DOMAIN,
    MYNEATO_LOGIN,
    MYNEATO_FLOORPLANS,
    MYNEATO_ROBOTS,
    SCAN_INTERVAL_MINUTES,
)
from .hub import MyNeatoHub

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)
ATTR_GENERATED_AT = "last_modified_at"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MyNeato camera with config entry."""
    dev = []
    neato: MyNeatoHub = hass.data[MYNEATO_LOGIN]
    floorplans: dict[str, Any] | None = hass.data.get(MYNEATO_FLOORPLANS)
    for robot in hass.data[MYNEATO_ROBOTS]:
        dev.append(NeatoCleaningMap(neato, robot, floorplans))

    if not dev:
        return

    _LOGGER.debug("Adding robots for cleaning maps %s", dev)
    async_add_entities(dev, True)


class NeatoCleaningMap(Camera):
    """Neato cleaning map for last clean."""

    def __init__(
        self, neato: MyNeatoHub, robot: Robot, floorplans: dict[str, Any] | None
    ) -> None:
        """Initialize Neato cleaning map."""
        super().__init__()
        self.robot = robot
        self.neato = neato
        self._floorplans = floorplans
        self._available = neato is not None
        self._robot_name = f"{self.robot.name} Cleaning Map"
        self._robot_serial: str = self.robot.serial
        self._last_modified_at: str | None = None
        self._image: bytes | None = None

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return image response."""
        self.update()
        return self._image

    def update(self) -> None:
        """Check the contents of the map list."""

        _LOGGER.debug("Running camera update for '%s'", self.entity_id)
        try:
            self.neato.update_robots()
        except MyNeatoRobotException as ex:
            if self._available:  # Print only once when available
                _LOGGER.error(
                    "Neato camera connection error for '%s': %s", self.entity_id, ex
                )
            self._image = None
            self._available = False
            return

        if self._floorplans:
            map_data: dict[str, Any] = self._floorplans[0]

        try:
            rank_image: bytes = map_data.rank_image
        except MyNeatoRobotException as ex:
            if self._available:  # Print only once when available
                _LOGGER.error(
                    "Neato camera connection error for '%s': %s", self.entity_id, ex
                )
            self._image = None
            self._available = False
            return

        if rank_image == self._image:
            _LOGGER.debug(
                "The map rank_image for '%s' is the same as old", self.entity_id
            )
            return

        self._image = rank_image
        self._last_modified_at = map_data.last_modified_at
        self._available = True

    @property
    def name(self) -> str:
        """Return the name of this camera."""
        return self._robot_name

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._robot_serial

    @property
    def available(self) -> bool:
        """Return if the robot is available."""
        return self._available

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for neato robot."""
        return DeviceInfo(identifiers={(MYNEATO_DOMAIN, self._robot_serial)})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        data: dict[str, Any] = {}

        if self._last_modified_at is not None:
            data[ATTR_GENERATED_AT] = self._last_modified_at

        return data
