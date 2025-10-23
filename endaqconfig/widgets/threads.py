"""
Threads used by the Device Dialog, for display updating and sending
simple commands to devices in the background.
"""

import threading
from time import sleep, time
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

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
    Thread that collects devices, connected via USB (MSD and serial) and
    MQTT.
    """

    def __init__(self,
                 parent: "DeviceSelectionDialog",
                 interval: float = 3):
        """
        Thread that collects devices, connected via USB and MQTT.

        :param parent: The parent dialog.
        :param interval: Time (seconds) between scans for devices. 0 or
            `None` will run once.
        """
        self.parent = parent
        self.interval = interval

        self.paused = threading.Event()  # Set to pause the scanning
        self.stop = threading.Event()  # Set to kill the thread
        self.mqttUpdated = threading.Event()  # Set when the set of MQTT devices changes
        self.updating = threading.RLock()
        self.updateThreads: Dict[Recorder, "DeviceCommandThread"] = {}
        self.updateCancelled = threading.Event()

        self.lastScan: float = 0.0
        self.lastMqttGet: float = 0.0  # last time parent.connector.getDevices() called
        self.mqttDevices = set()  # Last found MQTT devices
        self.lastMqttSerials = set()  # Serial numbers of known MQTT devices
        self.devices = set()  # All found devices, USB and MQTT

        super().__init__(daemon=True)
        self.name = self.name.replace('Thread', type(self).__name__)

        self.mqttUpdated.set()


    def onUpdate(self, update: dict):
        """
        Called by the `MQTTConnector` when an update arrives. The parent
        must supply this to `MQTTConnector` during its instantiation (via
        the `updateCallback` argument).

        :param update: A dictionary of data, the ``EBMLResponse`` content of
            a `MQTTDeviceManager` state update message.
        """
        try:
            print(update.get('DeviceList'))
            sns = set(d.get('SerialNumber') for d in update['DeviceList']['DeviceListItem'])
            if sns != self.lastMqttSerials:
                logger.debug('Got update from Manager; devices changed')
                self.lastMqttSerials = sns
                self.mqttUpdated.set()
            elif set(d.serialInt for d in self.parent.recorders).difference(sns):
                # XXX: Occasionally reported devices unchanged but some not shown... not sure why, so here's a hack
                logger.debug('Got update from Manager; same devices, but some not displayed?')
                self.lastMqttSerials = sns
                self.mqttUpdated.set()
            else:
                logger.debug('Got update from Manager; same devices')
        except KeyError:
            pass


    def stopped(self):
        """ Has the thread either stopped or in the process of stopping?
        """
        return not self.is_alive() or self.stop.is_set() or self.parent.isDead()


    def scan(self):
        """ Collect found devices.
        """
        self.lastScan = now = time()
        devices = set()

        # logger.debug('Collecting USB devices...')
        localdevs = getDevices()
        devices.update(localdevs)

        connected = self.parent.connector and self.parent.connector.client.is_connected()

        if connected and (self.mqttUpdated.is_set() or now - self.lastMqttGet > 30):
            logger.debug('Collecting MQTT devices...')
            try:
                self.parent.connector.exclude = {d.serialInt for d in localdevs}
                mqttDevices = set(self.parent.connector.getDevices(callback=self.stopped))
                with self.updating:
                    self.mqttDevices = mqttDevices
                    self.lastMqttGet = now
            except TimeoutError:
                logger.debug('timed out getting MQTT devices')

        self.mqttUpdated.clear()
        devices.update(self.mqttDevices)

        with self.updating:
            currentThreads = {}

            # Check if any previous update threads failed and collect any
            # that are still running (although they should all be done by now,
            # either successfully or had the command time out)
            for dev, thread in self.updateThreads.items():
                if thread.failed.is_set():
                    logger.debug(f'Update thread for {dev} failed: {thread.failure!r}')
                elif dev in devices and thread.is_alive():
                    currentThreads[dev] = thread

            self.devices = devices

        with self.updating:
            for dev in self.devices:
                if dev not in self.updateThreads:
                    currentThreads[dev] = DeviceCommandThread(dev, updateDeviceStatus, dev, callback=self.stopped)
            self.updateThreads = currentThreads


    def run(self):
        """ Main loop.
        """
        while not self.stop.is_set():
            if self.paused.is_set():
                sleep(0.1)
                continue

            now = time()
            if not self.interval or now - self.lastScan > self.interval or self.mqttUpdated.is_set():
                self.scan()

            if not self.interval:
                return

            sleep(1)


    def getDevices(self) -> List[Recorder]:
        """ Get a list of all active devices.
        """
        with self.updating:
            return sorted(self.devices, key=lambda x: x.serialInt)


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

        self.completed = threading.Event()  # Set upon successful completion
        self.result: Any = None  # The result of the function (if any)
        self.failed = threading.Event()  # Set if command raises an exception
        self.failure: Optional[Exception] = None  # Exception raised by the command (if any)

        super().__init__(daemon=True)
        self.name = self.name.replace('Thread', type(self).__name__)
        self.start()


    def run(self):
        try:
            self.result = self.command(*self.args, **self.kwargs)
            self.completed.set()
            # logger.debug(f'{self.name}: {self.device} '
            #              f'{self.command.__name__} succeeded')
        except Exception as err:
            self.failed.set()
            self.failure = err
            logger.error(f'{self.name}: {self.device} '
                         f'{self.command.__name__} failed: {err!r}')


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

    if type(device.command) is SerialCommandInterface:
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

    try:
        # This will read and cache the calibration data.
        # XXX: What if the userpage is updated?
        device.getCalExpiration()
    except (DeviceError, AttributeError, IOError, TimeoutError):
        pass


def getDeviceStatus(device: Recorder) \
        -> Tuple[Optional[Tuple],
                 Tuple[Optional[int], str],
                 Optional[str],
                 Optional[int],
                 bool,
                 bool]:
    """ Get the device's cached battery info, status, lock ID, and command
        interface availability in a form that can be hashed and easily tested
        for changes. Note that this only uses the current status; it does
        not ping the device to update it.

        :return: A tuple containing the device's battery status, status code
            and message, path, lock ID, command interface availability and
            whether it has read calibration data yet.
    """
    if not device.hasCommandInterface:
        # Old devices won't have a CommandInterface.
        return (None, (DeviceStatusCode.IDLE, ''), None, None, True, True)

    # All command interfaces have _battery, status, and lockId, but only
    # newer serial and MQTT interfaces set them. Older devices will set
    # status, but it will be the same as the command response.
    cmd = device.command
    bat = cmd._battery[1]
    if isinstance(bat, dict):
        bat = tuple(bat.values())
    return (bat, cmd.status[1:], device.path, cmd.lockId,
            device.command.available, bool(device._calibration))
