"""Support for Neato Connected Vacuums."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any
from pyneato.enum import CleaningModeEnum

import voluptuous as vol

from pyneato import (
    Robot,
    RobotState,
    MyNeatoRobotException,
    RobotStateEnum,
    RobotActionEnum
)

from homeassistant.components.vacuum import (
    ATTR_STATUS,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODE, STATE_IDLE, STATE_PAUSED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTION,
    ALERTS,
    ERRORS,
    MODE,
    MYNEATO_DOMAIN,
    MYNEATO_LOGIN,
    MYNEATO_FLOORPLANS,
    MYNEATO_ROBOTS,
    SCAN_INTERVAL_MINUTES,
)
from .hub import MyNeatoHub

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)

ATTR_CLEAN_START = "clean_start"
ATTR_CLEAN_STOP = "clean_stop"
ATTR_CLEAN_AREA = "clean_area"
ATTR_CLEAN_BATTERY_START = "battery_level_at_clean_start"
ATTR_CLEAN_BATTERY_END = "battery_level_at_clean_end"
ATTR_CLEAN_SUSP_COUNT = "clean_suspension_count"
ATTR_CLEAN_SUSP_TIME = "clean_suspension_time"
ATTR_CLEAN_PAUSE_TIME = "clean_pause_time"
ATTR_CLEAN_ERROR_TIME = "clean_error_time"
ATTR_LAUNCHED_FROM = "launched_from"

ATTR_NAVIGATION = "navigation"
ATTR_CATEGORY = "category"
ATTR_ZONE = "zone"
ATTR_MODE = "mode"
ATTR_TRACK = "track"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MyNeato vacuum with config entry."""
    dev = []
    neato: MyNeatoHub = hass.data[MYNEATO_LOGIN]
    floorplans: dict[str, Any] | None = hass.data.get(MYNEATO_FLOORPLANS)
    for robot in hass.data[MYNEATO_ROBOTS]:
        dev.append(MyNeatoVacuum(neato, robot, floorplans))

    if not dev:
        return

    _LOGGER.debug("Adding vacuums %s", dev)
    async_add_entities(dev, True)

    platform = entity_platform.async_get_current_platform()
    assert platform is not None

    platform.async_register_entity_service(
        "custom_cleaning",
        {
            vol.Optional(ATTR_MODE, default=CleaningModeEnum.ECO.value): cv.string,
            vol.Optional(ATTR_TRACK): cv.string,
        },
        "myneato_custom_cleaning",
    )


class MyNeatoVacuum(StateVacuumEntity):
    """Representation of a Neato Connected Vacuum."""

    _attr_icon = "mdi:robot-vacuum-variant"
    _attr_supported_features = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.START
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.STATE
        # | VacuumEntityFeature.MAP
        | VacuumEntityFeature.LOCATE
    )

    def __init__(
        self,
        neato: MyNeatoHub,
        robot: Robot,
        floorplans: set | None,
    ) -> None:
        """Initialize the MyNeato Vacuum."""
        self.robot = robot
        self._attr_available: bool = neato is not None
        self._floorplans = floorplans
        self._attr_name: str = self.robot.name
        self._robot_has_map: bool = len(floorplans) > 0
        self._robot_serial: str = self.robot.serial
        self._attr_unique_id: str = self.robot.serial
        self._status_state: str | None = None
        self._clean_state: str | None = None
        self._state: RobotState | None = None
        self._clean_time_start: str | None = None
        self._clean_time_stop: str | None = None
        self._clean_area: float | None = None
        self._clean_battery_start: int | None = None
        self._clean_battery_end: int | None = None
        self._clean_susp_charge_count: int | None = None
        self._clean_susp_time: int | None = None
        self._clean_pause_time: int | None = None
        self._clean_error_time: int | None = None
        self._launched_from: str | None = None
        self._robot_boundaries: list = []
        self._robot_stats: dict[str, Any] | None = None

    def update(self) -> None:
        """Update the states of MyNeato Vacuums."""
        _LOGGER.debug("Running MyNeato Vacuums update for '%s'", self.entity_id)
        try:
            if self._robot_stats is None:
                self._robot_stats = self.robot.info_robot()
        except MyNeatoRobotException:
            _LOGGER.warning("Couldn't fetch robot information of %s", self.entity_id)

        try:
            self._state = self.robot.state
        except MyNeatoRobotException as ex:
            if self._attr_available:  # print only once when available
                _LOGGER.error(
                    "MyNeato vacuum connection error for '%s': %s", self.entity_id, ex
                )
            self._state = None
            self._attr_available = False
            return

        if self._state is None:
            return
        self._attr_available = True
        _LOGGER.debug("self._state=%s", self._state)

        robot_alert = None
        """
        if "alert" in self._state:
            robot_alert = ALERTS.get(self._state["alert"])
        else:
            robot_alert = None
        """

        if self._state.state == RobotStateEnum.IDLE:
            if self._state.details.is_charging:
                self._clean_state = STATE_DOCKED
                self._status_state = "Charging"
            elif (
                self._state.details.is_docked
                and not self._state.details.is_charging
            ):
                self._clean_state = STATE_DOCKED
                self._status_state = "Docked"
            else:
                self._clean_state = STATE_IDLE
                self._status_state = "Stopped"

            if robot_alert is not None:
                self._status_state = robot_alert
        elif self._state.state == RobotStateEnum.BUSY:
            if robot_alert is None:
                self._clean_state = STATE_CLEANING
                """
                self._status_state = (
                    f"{MODE.get(self._state['cleaning']['mode'])} "
                    f"{ACTION.get(self._state.action)}"
                )
                if (
                    "boundary" in self._state["cleaning"]
                    and "name" in self._state["cleaning"]["boundary"]
                ):
                    self._status_state += (
                        f" {self._state['cleaning']['boundary']['name']}"
                    )
                """
            else:
                self._status_state = robot_alert
        elif self._state.state == RobotStateEnum.PAUSED:
            self._clean_state = STATE_PAUSED
            self._status_state = "Paused"
        elif self._state.state == RobotStateEnum.ERROR:
            self._clean_state = STATE_ERROR
            self._status_state = ERRORS.get(self._state["error"])

        self._attr_battery_level = self._state.details.charge

        """
        if self._floorplans is None or not self._floorplans.get(self._robot_serial, {}).get(
            "maps", []
        ):
            return

        floorplan: dict[str, Any] = self._floorplans[self._robot_serial]["maps"][0]
        self._clean_time_start = floorplan["start_at"]
        self._clean_time_stop = floorplan["end_at"]
        self._clean_area = floorplan["cleaned_area"]
        self._clean_susp_charge_count = floorplan["suspended_cleaning_charging_count"]
        self._clean_susp_time = floorplan["time_in_suspended_cleaning"]
        self._clean_pause_time = floorplan["time_in_pause"]
        self._clean_error_time = floorplan["time_in_error"]
        self._clean_battery_start = floorplan["run_charge_at_start"]
        self._clean_battery_end = floorplan["run_charge_at_end"]
        self._launched_from = floorplan["launched_from"]

        if (
            self._robot_has_map
            and self._floorplans
            and self._state
        ):
            allmaps: dict = self._floorplans
            _LOGGER.debug(
                "Found the following maps for '%s': %s", self.entity_id, allmaps
            )

            for maps in allmaps:
                try:
                    robot_boundaries = self.robot.get_map_boundaries(maps["id"]).json()
                except MyNeatoRobotException as ex:
                    _LOGGER.error(
                        "Could not fetch map boundaries for '%s': %s",
                        self.entity_id,
                        ex,
                    )
                    return

                _LOGGER.debug(
                    "Boundaries for robot '%s' in map '%s': %s",
                    self.entity_id,
                    maps["name"],
                    robot_boundaries,
                )
                if "boundaries" in robot_boundaries["data"]:
                    self._robot_boundaries += robot_boundaries["data"]["boundaries"]
                    _LOGGER.debug(
                        "List of boundaries for '%s': %s",
                        self.entity_id,
                        self._robot_boundaries,
                    )
        """

    @property
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self._clean_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        data: dict[str, Any] = {}

        if self._status_state is not None:
            data[ATTR_STATUS] = self._status_state
        if self._clean_time_start is not None:
            data[ATTR_CLEAN_START] = self._clean_time_start
        if self._clean_time_stop is not None:
            data[ATTR_CLEAN_STOP] = self._clean_time_stop
        if self._clean_area is not None:
            data[ATTR_CLEAN_AREA] = self._clean_area
        if self._clean_susp_charge_count is not None:
            data[ATTR_CLEAN_SUSP_COUNT] = self._clean_susp_charge_count
        if self._clean_susp_time is not None:
            data[ATTR_CLEAN_SUSP_TIME] = self._clean_susp_time
        if self._clean_pause_time is not None:
            data[ATTR_CLEAN_PAUSE_TIME] = self._clean_pause_time
        if self._clean_error_time is not None:
            data[ATTR_CLEAN_ERROR_TIME] = self._clean_error_time
        if self._clean_battery_start is not None:
            data[ATTR_CLEAN_BATTERY_START] = self._clean_battery_start
        if self._clean_battery_end is not None:
            data[ATTR_CLEAN_BATTERY_END] = self._clean_battery_end
        if self._launched_from is not None:
            data[ATTR_LAUNCHED_FROM] = self._launched_from

        return data

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for neato robot."""
        return DeviceInfo(
            identifiers={(MYNEATO_DOMAIN, self._robot_serial)},
            manufacturer=self.robot.vendor.friendly_name,
            model=self.robot.model_name,
            name=self._attr_name,
            sw_version=self.robot.firmware,
        )

    def start(self) -> None:
        """Start cleaning or resume cleaning."""
        if self._state:
            try:
                if self._state.state == RobotStateEnum.IDLE:
                    self.robot.start_cleaning(self._floorplans[0])
                elif self._state.state == RobotStateEnum.PAUSED:
                    self.robot.resume_cleaning()
            except MyNeatoRobotException as ex:
                _LOGGER.error(
                    "Neato vacuum connection error for '%s': %s", self.entity_id, ex
                )

    def pause(self) -> None:
        """Pause the vacuum."""
        try:
            self.robot.pause_cleaning()
        except MyNeatoRobotException as ex:
            _LOGGER.error(
                "Neato vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        try:
            if self._clean_state == STATE_PAUSED:
                self.robot.return_to_base()
            else:
                self.robot.cancel_cleaning()

            self._clean_state = STATE_RETURNING
        except MyNeatoRobotException as ex:
            _LOGGER.error(
                "Neato vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        try:
            self.robot.cancel_cleaning()
        except MyNeatoRobotException as ex:
            _LOGGER.error(
                "Neato vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def locate(self, **kwargs: Any) -> None:
        """Locate the robot by making it emit a sound."""
        try:
            self.robot.find_me()
        except MyNeatoRobotException as ex:
            _LOGGER.error(
                "Neato vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def clean_spot(self, **kwargs: Any) -> None:
        """Run a spot cleaning starting from the base."""
        try:
            """self.robot.start_spot_cleaning()"""
        except MyNeatoRobotException as ex:
            _LOGGER.error(
                "Neato vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def neato_custom_cleaning(
        self, mode: str, navigation: str, category: str, zone: str | None = None
    ) -> None:
        """Zone cleaning service call."""

        """
        boundary_id = None
        if zone is not None:
            for boundary in self._robot_boundaries:
                if zone in boundary["name"]:
                    boundary_id = boundary["id"]
            if boundary_id is None:
                _LOGGER.error(
                    "Zone '%s' was not found for the robot '%s'", zone, self.entity_id
                )
                return
            _LOGGER.info("Start cleaning zone '%s' with robot %s", zone, self.entity_id)

        self._clean_state = STATE_CLEANING
        try:
            self.robot.start_cleaning(mode, navigation, category, boundary_id)
        except MyNeatoRobotException as ex:
            _LOGGER.error(
                "Neato vacuum connection error for '%s': %s", self.entity_id, ex
            )
        """
