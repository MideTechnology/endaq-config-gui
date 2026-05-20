"""
Threads used by the Device Dialog, for display updating and sending
simple commands to devices in the background.
"""

from functools import partial
import socket
import threading
from time import sleep, time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

from endaq.device import (Recorder, getDevices, DeviceError, CommandError,
                          CommunicationError, UnsupportedFeature)
from endaq.device.command_interfaces import SerialCommandInterface
from endaq.device.mqtt.mqtt_interface import MQTTConnector
from endaq.device.response_codes import DeviceStatusCode

import logging
logger = logging.getLogger(__name__)

import wx

from endaqconfig.widgets.events import (EvtMQTTConnecting, EvtMQTTConnected,
                                        EvtMQTTDisconnected, EvtMQTTError,
                                        EvtBrokerSelected)

# from .debug_lock import DebugRLock

# noinspection PyUnusedImports
if TYPE_CHECKING:
    from .device_dialog import DeviceSelectionDialog
    from .broker_dialog import BrokerDialog


# ===========================================================================
#
# ===========================================================================

class DeviceScanThread(threading.Thread):
    """
    Thread that collects devices, connected via USB (MSD and serial) and
    MQTT.
    """

    # For debugging, to make it clear in the log if a thread is new
    _INDEX = 0

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
        self.updateThreads: Dict[Recorder, "DeviceCommandThread"] = {}
        self.updateCancelled = threading.Event()

        self.updating = threading.RLock()

        self.lastScan: float = 0.0
        self.lastMqttGet: float = 0.0  # last time parent.connector.getDevices() called
        self.mqttDevices = set()  # Last found MQTT devices
        self.lastMqttSerials = set()  # Serial numbers of known MQTT devices
        self.devices = set()  # All found devices, USB and MQTT

        self.deviceStatus: dict[Recorder, tuple] = {}

        DeviceScanThread._INDEX += 1
        super().__init__(name=f'{type(self).__name__}-{DeviceScanThread._INDEX}',
                         daemon=True)

        self.mqttUpdated.set()
        # logger.debug(f'Created {self.name}')


    def clearCache(self):
        """ Clear cached recorders and related data.
        """
        self.deviceStatus.clear()
        self.mqttDevices.clear()
        self.lastMqttSerials.clear()
        self.devices.clear()


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
            # logger.debug('Collecting MQTT devices...')
            try:
                self.parent.connector.exclude = {d.serialInt for d in localdevs}
                mqttDevices = set(self.parent.connector.getDevices(offline=True,
                                                                   managerTimeout=300,
                                                                   callback=self.stopped))
                with self.updating:
                    self.mqttDevices = mqttDevices
                    self.lastMqttGet = now
            except TimeoutError:
                logger.debug('timed out getting MQTT devices')

            logger.debug('Got MQTT devices.')

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
            # logger.debug('Starting updateDeviceStatus threads')
            # XXX: Skip update for timed out devices?
            for dev in self.devices.copy():
                if not isOnline(dev):
                    continue
                elif isSleeping(dev):
                    continue

                if dev not in self.updateThreads:
                    currentThreads[dev] = DeviceCommandThread(dev, updateDeviceStatus,
                                                              dev, callback=self.stopped)

            self.updateThreads = currentThreads


    def run(self):
        """ Main loop.
        """
        logger.debug(f'Starting main loop of {self.name}')
        while not self.stop.is_set():
            if self.paused.is_set():
                sleep(0.1)
                continue

            try:
                now = time()
                if (not self.interval
                        or now - self.lastScan > self.interval
                        or self.mqttUpdated.is_set()):
                    self.scan()

                if not self.interval:
                    # One-off scan
                    break

            except Exception:
                logger.exception('Error in DeviceScanThread loop, continuing')

            sleep(1)
        logger.debug(f'Exiting main loop of {self.name}')


    def getDevices(self) -> List[Recorder]:
        """ Get a list of all active devices.
        """
        devs = self.devices.copy()
        return sorted(devs, key=lambda x: x.serialInt)


    def getDeviceStatuses(self):
        return {dev: getDeviceStatus(dev) for dev in self.devices.copy()}


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

        super().__init__(name=f'{type(self).__name__}_{device.serial} ({command.__name__})',
                         daemon=True)
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
        if device.command.status[1] in (DeviceStatusCode.IDLE, DeviceStatusCode.IDLE_UNMOUNTED):
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
        for changes. Note that this only uses the current/last reported
        status; it does not ping the device to update it.

        :return: A tuple containing the device's battery status, status code
            and message, path, lock ID, command interface availability, and
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
    return (bat, cmd.status[1:], device.path, cmd.lockId[1],
            bool(device._calibration))


def isOnline(device: Recorder) -> bool:
    """ Is the device in an 'online' state? Note that local USB devices are
        inherently online.
    """
    if device.isVirtual:
        return False
    elif not device.isRemote:
        return True

    # TODO: Also exclude timed out devices?
    status = device.command.status[1]
    if status is not None and 300 <= status < 500:
        # Codes 400-499 are 'offline' variants of positive codes 0-99
        return False
    return status not in (DeviceStatusCode.ERR_DISCONNECTED,
                          DeviceStatusCode.OFFLINE,
                          DeviceStatusCode.RESET_PENDING,
                          DeviceStatusCode.START_PENDING,
                          DeviceStatusCode.STOP_PENDING,
                          DeviceStatusCode.UPLOADING,
                          None)


def isSleeping(device: Recorder) -> bool:
    """ Is the device in a 'sleeping' state?
    """
    status = device.command.status[1]
    if status is not None and 200 <= status < 400:
        # Codes 300-399 are 'periodic' variants of positive codes 0-99
        return True
    return status in (DeviceStatusCode.SLEEPING,
                      DeviceStatusCode.WAKING)


def isGateway(device: Recorder) -> bool:
    """ Is the device a HDS Gateway box?
    """
    # Gateway-ness determined by bits in the "recorder's" `RecorderTypeUID`.
    devtype = device.getInfo('RecorderTypeUID', 0)
    return bool(devtype & 0xa0000000)  # bits 31 (non-recorder) and 29 (gateway)


# ===========================================================================
#
# ===========================================================================

class BrokerConnectThread(threading.Thread):
    """
    Mechanism to connect to a broker. Auto-starts on instantiation. Stops
    after posting an event.

    Posts events to its 'parent' (usually a `BrokerDialog`, but will be the
    root `DeviceSelectionDialog` when it opens with "Show remote devices"
    checked).
    """

    def __init__(self,
                 parent: Union["DeviceSelectionDialog", "BrokerDialog"],
                 root: Union["DeviceSelectionDialog", "BrokerDialog"],
                 brokerInfo: Dict[str, Any],
                 **connectorArgs,
                 ):
        """ Mechanism to connect to a broker. Auto-starts on instantiation.
            Keyword arguments not listed below are passed to the
            instantiation of the `MQTTConnector`.

            :param parent: The parent dialog (a `BrokerDialog` or
                `DeviceSelectionDialog`).
            :param root: The 'root' `DeviceSelectionDialog`. Can be the same
                as `parent` if thread started by it.
            :param brokerInfo: The info about the selected broker (e.g., from
                `endaq.device.mqtt.discovery.findBrokers()`).
        """
        self.parent = parent
        self.root = root
        self.info = brokerInfo
        self.connectorArgs = dict(connectorArgs)
        self.stop = threading.Event()  # Set to kill the thread

        super().__init__(daemon=True)
        self.name = f'BrokerConnect{self.name}'

        self.start()


    def run(self):
        wx.PostEvent(self.parent, EvtMQTTConnecting(info=self.info))
        onConnect = partial(postCallbackEvent, EvtMQTTConnected, self.root)
        onDisconnect = partial(postCallbackEvent, EvtMQTTDisconnected, self.root)
        onConnect.__name__ = 'EvtMQTTConnected'
        onDisconnect.__name__ = 'EvtMQTTDisconnected'

        kwargs = self.connectorArgs
        kwargs.update(self.info)
        kwargs['connectCallback'] = onConnect
        kwargs['disconnectCallback'] = onDisconnect

        try:
            con = MQTTConnector(**kwargs)

        except TimeoutError as err:
            self.postError('Timeout connecting to broker', err)
            return
        except CommunicationError as err:
            self.postError('Could not connect to broker', err)
            return
        except Exception as err:
            self.postError(str(err), err)
            return

        # Connected to the broker; check the `MQTTDeviceManager`
        try:
            con.command.ping()
            wx.PostEvent(self.parent, EvtBrokerSelected(connector=con,
                                                        info=self.info))

        except (CommunicationError, TimeoutError) as err:
            self.postError("Could not contact enDAQ Device Manager", err)

        except socket.gaierror as err:
            self.postError(f"Could not resolve hostname", err)

        except ConnectionRefusedError as err:
            self.postError("Connection refused", err)

        except Exception as err:
            self.postError(str(err), err)


    def postError(self, message: str, err: Exception):
        """ Post an `EVT_MQTT_ERROR` event.
        """
        try:
            wx.PostEvent(self.parent,
                         EvtMQTTError(message=message, exception=err))
        except RuntimeError as e:
            # Possibly called while changing windows or cleaning up,
            # which is (probably) okay.
            logger.debug(f'Ignoring failure posting  to {self.parent}: {e}')
            pass


def postCallbackEvent(eventType: type[wx.Event],
                      target: Union["DeviceSelectionDialog", "BrokerDialog"],
                      *args):
    """ Post an event in response to an MQTT connect or disconnect callback.
        Meant to be set as `MQTTConnector.onConnect` or `MQTTConnector.onDisconnect`
        after using `partial` to set the `eventType` and `target`. Other
        arguments (the MQTT client callback arguments) are sent in the
        posted event.

        :param eventType: The MQTT event class to post (e.g.,
            `events.EvtMQTTConnected` or `events.EvtMQTTDisconnected`)
        :param target: The dialog to which to post the event.
    """
    if not target:
        # Can happen in testing, shouldn't happen elsewhere
        logger.debug('postCallbackEvent: No target specified!')
        return
    try:
        # noinspection PyArgumentList
        wx.PostEvent(target, eventType(args=args))
    except RuntimeError as evt:
        # Possibly called while changing windows or cleaning up,
        # which is (probably) okay.
        logger.debug(f'Ignoring failure posting {eventType.__name__} to {target}: {evt}')
        pass
