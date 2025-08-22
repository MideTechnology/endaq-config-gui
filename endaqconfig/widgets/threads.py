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
