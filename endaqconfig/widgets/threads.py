"""
Threads used by the Device Dialog, for display updating and sending
simple commands to devices in the background.
"""

import threading
from time import sleep, time
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from endaq.device import (Recorder, getDevices, DeviceError,
                          CommandError, UnsupportedFeature)
from endaq.device.command_interfaces import SerialCommandInterface
from endaq.device.response_codes import DeviceStatusCode

import logging
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .device_dialog import DeviceSelectionDialog


# ===========================================================================
#
# ===========================================================================

class DeviceScanThread(threading.Thread):
    """
    Thread that collects devices, connected via USB and MQTT.
    """

    def __init__(self,
                 parent: "DeviceSelectionDialog",
                 interval: float = 3):
        """
        Thread that collects devices, connected via USB and MQTT.

        :param parent: The parent dialog.
        :param interval: Time (seconds) between scans for devices.
        """
        self.parent = parent
        self.interval = interval

        self.paused = threading.Event()  # Set to pause the scanning
        self.stop = threading.Event()  # Set to kill the thread
        self.mqttUpdated = threading.Event()  # Set when an update from the Device Manager arrives
        self.updating = threading.RLock()

        self.mqttDevices = set()  # Last found MQTT devices
        self.lastMqttSerials = set()  # Serial numbers of known MQTT devices
        self.devices = set()  # All found devices, USB and MQTT

        super().__init__(daemon=True)
        self.name = self.name.replace('Thread', type(self).__name__)

        self.mqttUpdated.set()
        # self.start()


    def onUpdate(self, devices: List[int]):
        """
        Called by the `MQTTConnector` when an update arrives. The parent
        must supply this to `MQTTConnector` during its instantiation.

        :param devices:
        :return:
        """
        # XXX: Modify MQTTConnector._onManagerState() to send list of all SN
        #  in the message instead of existing device instances
        devices = set(devices)
        if devices != self.lastMqttSerials:
            self.lastMqttSerials = devices
            self.mqttUpdated.set()


    def run(self):
        """ Main loop. """
        while not self.stop.is_set():
            if self.paused.is_set():
                sleep(0.1)
                continue

            devices = set()

            if (self.mqttUpdated.is_set()
                    and self.parent.connector
                    and self.parent.connector.client.is_connected()):
                self.mqttUpdated.clear()
                try:
                    self.mqttDevices = set(self.parent.connector.getDevices())
                except TimeoutError:
                    logger.debug('timed out getting MQTT devices')

            devices.update(self.mqttDevices)
            devices.update(getDevices())

            with self.updating:
                self.devices = devices

            sleep(self.interval)


    def getDevices(self) -> List[Recorder]:
        """ Get a list of all active devices.
        """
        with self.updating:
            return sorted(self.devices, key=lambda x: x.serialNumberInt)


# ===========================================================================
#
# ===========================================================================

class DeviceCommandThread(threading.Thread):
    """
    A slightly safer-than-normal thread for asynchronously calling simple
    `Recorder` methods. Exceptions are caught and kept for later handing.

    Note: Threads start immediately upon instantiation!
    """

    def __init__(self,
                 device: Recorder,
                 command: Callable,
                 *args,
                 **kwargs):
        """ A slightly safer-than-normal thread for asynchronously calling
            simple `Recorder` methods. Note that threads start immediately
            upon instantiation!

            :param device: The device running the command.
            :param command: The function/method to call.

            Other arguments/keyword arguments are used when calling `command`
            (like `functools.partial`).
        """
        self.device = device
        self.command = command
        self.args = args
        self.kwargs = kwargs
        self.failed = threading.Event()  # Set if command raises an exception
        self.completed = threading.Event()  # Set upon successful completion
        self.failure = None  # Exception raised by the command (if any)

        super().__init__(daemon=True)
        self.start()


    def run(self):
        try:
            self.command(*self.args, **self.kwargs)
            self.completed.set()
            logger.debug(f'DeviceCommandThread: {self.device} {self.command.__name__} succeeded')
        except Exception as err:
            self.failed.set()
            self.failure = err
            logger.error(f'DeviceCommandThread: {self.device} {self.command.__name__} failed: {err!r}')


# ===========================================================================
#
# ===========================================================================

def updateDeviceStatus(device: Recorder, callback: Callable, timeout=1):
    """ Get updated status and battery info (if available) from the device
        via serial (filesystem-based devices don't report status, MQTT
        devices automatically update themselves).

        This is intended to be run in its own thread for asynchronicity.
    """
    if not device.hasCommandInterface:
        # Very old firmware and/or no serial command interface.
        return
    if type(device.command) is not SerialCommandInterface:
        return

    try:
        device.command.getBatteryStatus(timeout=timeout, callback=callback)
    except CommandError:
        # Older FW that doesn't support GetBatteryStatus returns
        # ERR_INVALID_COMMAND. Try to `ping` to get status.
        try:
            device.command.ping(timeout=timeout, callback=callback)
        except (DeviceError, AttributeError, IOError):
            pass
    except (NotImplementedError, UnsupportedFeature):
        pass
    except TimeoutError:
        logger.debug(f'updateDeviceStatus(): Timed out updating {device}')
        pass


def getDeviceStatus(device: Recorder) \
        -> Tuple[Optional[Tuple],
                 Tuple[Optional[int], str],
                 Optional[str], Optional[int],
                 bool]:
    """ Get the device's cached battery info, status, lock ID, and command
        interface availability in a form that can be hashed and easily tested
        for changes.
    """
    if not device.hasCommandInterface:
        # Old devices won't have a CommandInterface.
        return (None, (DeviceStatusCode.IDLE, ''), None, None, True)

    # All command interfaces have _battery, status, and lockId, but only
    # newer serial and MQTT interfaces set them. Older devices will set
    # status, but it will be the same as the command response.
    cmd = device.command
    bat = cmd._battery[1]
    if isinstance(bat, dict):
        bat = tuple(bat.values())
    return (bat, cmd.status[1:], device.path, cmd.lockId, device.command.available)
