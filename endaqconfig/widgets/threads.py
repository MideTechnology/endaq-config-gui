"""
Threads used by the Device Dialog, for display updating and sending
simple commands to devices in the background.
"""

import threading
from time import sleep, time
from typing import Callable, Optional, Union

from endaq.device import (Recorder, getDevices,
                          deviceChanged, UnsupportedFeature, DeviceError,
                          CommandError, DeviceTimeout)
from endaq.device.response_codes import DeviceStatusCode
import wx

from .events import EvtDeviceListUpdate

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .device_dialog import DeviceSelectionDialog

import logging
logger = logging.getLogger(__name__)


# ===========================================================================
#
# ===========================================================================

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
                 timeout: Optional[float] = 4,
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
                and no longer appears in `getDevices()`. Prevents devices
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
        updatingSet = self.parent.updating.is_set
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
                        stat = dev.command.status
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
                            stat = dev.command.status
                        except (DeviceError, AttributeError, IOError):
                            bat = None
                            stat = DeviceStatusCode.IDLE, None

                    # logger.debug(f'{dev} {bat=} {stat=}')
                    status[dev] = bat, stat, dev.path

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
            logger.debug(f'{self.command} succeeded')
        except Exception as err:
            self.failed.set()
            self.failure = err
            logger.error(f'{self.command} failed: {err!r}')
