"""
Threads used by the Device Dialog, for display updating and sending
simple commands to devices in the background.
"""

import threading
from time import sleep, time
from typing import Callable, List, Optional, Tuple, Union, TYPE_CHECKING

from endaq.device import (Recorder, getDevices, deviceChanged, DeviceError,
                          CommandError, DeviceTimeout, UnsupportedFeature)
from endaq.device.command_interfaces import SerialCommandInterface
from endaq.device.response_codes import DeviceStatusCode

import wx

# from .events import EvtDeviceListUpdate

import logging
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .device_dialog import DeviceSelectionDialog


# ===========================================================================
#
# ===========================================================================

# XXX: REMOVE DeviceScanThread (after making sure all functionality has been
#  implemented in OnUpdateTimerTick)
class DeviceScanThread(threading.Thread):
    """
    A background thread for finding devices and their states. It can be
    stopped by calling `DeviceScanThread.stop()`.
    """

    def __init__(self,
                 parent: "DeviceSelectionDialog",
                 devFilter: Optional[Callable] = None,
                 interval: Union[int, float] = 3,
                 oneshot: bool = False,
                 timeout: float = 9,
                 **getDevicesArgs):
        """ A background thread for finding devices and their states. It can be
            stopped by calling `DeviceScanThread.stop()`.

            :param parent: The parent dialog.
            :param devFilter: A filter function to exclude devices.
            :param interval: Time (in milliseconds) between each full scan
                for changes to available devices (MSD, serial, etc.). Checks
                for drive changes are cheaper, and are run at half this
                interval.
            :param oneshot: If True, the thread will terminate after one
                scan. For doing manual updates.
            :param timeout: Seconds to retain devices that have disconnected
                and no longer appear in `getDevices()`. Prevents devices
                that momentarily disconnect when starting/stopping recording
                or resetting from disappearing and reappearing in the list.

            Additional keyword arguments are used when calling `getDevices()`.
        """
        super().__init__(name=type(self).__name__)
        self.daemon = True

        self.parent = parent
        self.interval = interval / 1000
        self.filter = devFilter
        self.oneshot = oneshot
        self.getDevicesArgs = getDevicesArgs

        self._cancel = threading.Event()
        self._cancel.clear()
        self._pause = threading.Event()
        self._pause.clear()

        self.timeout = timeout
        self.timeouts = {}


    def stop(self):
        logger.debug('Stopping scanning thread')
        self._cancel.set()


    def pause(self):
        logger.debug('Pausing scanning thread')
        self._pause.set()


    def resume(self):
        logger.debug('Resuming scanning thread')
        self._pause.clear()


    def paused(self):
        return self._pause.is_set()


    def run(self):
        """ The main loop.
        """
        logger.debug('Started scanning thread')

        updates = -1
        cancelSet = self._cancel.is_set
        pauseSet = self._pause.is_set
        updatingSet = self.parent.updatingDisplay.is_set
        timeout = self.timeout

        while bool(self.parent) and not cancelSet():
            updates += 1

            if pauseSet() or updatingSet():
                sleep(self.interval / 4)
                continue

            # Only do `getDevices()` every other time, or if the drives have
            # changed (`deviceChanged()` is cheap, `getDevices()` less so)
            if not self.oneshot and updates % 2 != 0 and not deviceChanged(recordersOnly=False):
                sleep(self.interval / 2)
                continue

            try:
                # TODO: Get MQTT devices!
                devices = getDevices()
                self.timeouts.update({dev: time() + timeout for dev in devices})
                result = [dev for dev, t in self.timeouts.items() if t > time()]

                status = {}
                if self.filter:
                    result = list(filter(self.filter, result))

                # TODO: Put status-getting for each device in its own thread
                #  and report only current `status` in the `EvtDeviceListUpdate`.
                #  Each thread would send a single event on completion.
                for dev in result:
                    # Not present, but not expired. Will show as disabled.
                    # Prevents devices disappearing and reappearing when
                    # starting/ending recordings.
                    if dev not in devices:
                        status[dev] = None, (None, None)
                        continue

                    elif not dev.hasCommandInterface:
                        status[dev] = None, (DeviceStatusCode.IDLE, None)
                        continue

                    try:
                        bat = dev.command.getBatteryStatus(callback=cancelSet)
                        stat = dev.command.status[1:]
                    except (NotImplementedError, UnsupportedFeature):
                        # Very old firmware and/or no serial command interface.
                        bat = None
                        stat = DeviceStatusCode.IDLE, None
                    except CommandError:
                        # Older FW that doesn't support GetBatteryStatus returns
                        # ERR_INVALID_COMMAND. Try to ping to get status.
                        try:
                            dev.command.ping(callback=cancelSet)
                            bat = None
                            stat = dev.command.status[1:]
                        except (DeviceError, AttributeError, IOError):
                            bat = None
                            stat = DeviceStatusCode.IDLE, None

                    # logger.debug(f'{dev} {bat=} {stat=}')
                    status[dev] = bat, stat, dev.path

                # logger.debug('posting EVT_DEVICE_LIST_UPDATE')
                evt = EvtDeviceListUpdate(devices=result, status=status)

                # Check parent again to avoid a race condition during shutdown
                if bool(self.parent):
                    wx.PostEvent(self.parent, evt)
                else:
                    logger.debug('Parent gone, did not post update event!')

            except DeviceTimeout:
                logger.warning("Timed out when scanning for devices, retrying")

            except DeviceError as E:
                if E.args and E.args[0] == DeviceStatusCode.ERR_BUSY:
                    logger.info("Device repoted ERR_BUSY, retrying")
                else:
                    logger.error(E)
                    raise

            except IOError as E:
                # TODO: Catch serial error(s), too?
                logger.warning(E)

            if self.oneshot:
                break

            sleep(self.interval)

        logger.debug('Scanning thread stopped')


    # =======================================================================
    #
    # =======================================================================

    def updateDeviceStatus(self, dev: Recorder):
        """ Update the device's cached status and battery info (if supported).
            If `getBatteryStatus()` isn't supported, `ping()` is used. To be
            run in a thread.
        """
        # TODO: Consider using asyncio instead of multiple threads.
        try:
            dev.command.getBatteryStatus(callback=self._cancel.is_set)
        except CommandError:
            # Older FW that doesn't support GetBatteryStatus returns
            # ERR_INVALID_COMMAND. Try to ping to get status.
            try:
                dev.command.ping(callback=self._cancel.is_set)
            except (DeviceError, AttributeError, IOError):
                pass
        except (NotImplementedError, UnsupportedFeature):
            pass


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

def getAllDevices(filterFunc: Optional[Callable] = None, **kwargs) -> List[Recorder]:
    """ Get all available devices.
    """
    # TODO: Get MQTT devices! Needs `update` implementation in `MQTTConnector.getDevices()`
    # This may become partially redundant with those changes, but keep for the filtering.
    devices = getDevices(**kwargs)

    if filterFunc is not None:
        return [d for d in devices if filterFunc(d)]

    return devices


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
