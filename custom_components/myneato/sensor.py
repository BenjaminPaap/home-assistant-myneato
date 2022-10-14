"""Support for Neato sensors."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyneato.exception import MyNeatoRobotException
from pyneato.robot import Robot

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MYNEATO_DOMAIN, MYNEATO_LOGIN, MYNEATO_ROBOTS, SCAN_INTERVAL_MINUTES
from .hub import MyNeatoHub

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)

BATTERY = "Battery"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Neato sensor using config entry."""
    dev = []
    neato: MyNeatoHub = hass.data[MYNEATO_LOGIN]
    for robot in hass.data[MYNEATO_ROBOTS]:
        dev.append(MyNeatoSensor(neato, robot))

    if not dev:
        return

    _LOGGER.debug("Adding robots for sensors %s", dev)
    async_add_entities(dev, True)


class MyNeatoSensor(SensorEntity):
    """Neato sensor."""

    def __init__(self, neato: MyNeatoHub, robot: Robot) -> None:
        """Initialize Neato sensor."""
        self.robot = robot
        self._available: bool = False
        self._robot_name: str = f"{self.robot.name} {BATTERY}"
        self._robot_serial: str = self.robot.serial
        self._state: dict[str, Any] | None = None

    def update(self) -> None:
        """Update Neato Sensor."""
        try:
            self._state = self.robot.state
        except MyNeatoRobotException as ex:
            if self._available:
                _LOGGER.error(
                    "Neato sensor connection error for '%s': %s", self.entity_id, ex
                )
            self._state = None
            self._available = False
            return

        self._available = True
        _LOGGER.debug("self._state=%s", self._state)

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return self._robot_name

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._robot_serial

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return SensorDeviceClass.BATTERY

    @property
    def entity_category(self) -> EntityCategory:
        """Device entity category."""
        return EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._available

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        if self._state is not None:
            return str(self._state.details.charge)
        return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement."""
        return PERCENTAGE

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for neato robot."""
        return DeviceInfo(identifiers={(MYNEATO_DOMAIN, self._robot_serial)})
