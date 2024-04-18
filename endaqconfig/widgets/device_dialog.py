"""
Dialog for selecting and/or controlling recording devices.

"""

from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from functools import partial
import logging
import os.path
import threading
from time import sleep, time
from typing import Callable, Optional, Union

import wx
import wx.lib.sized_controls as sc
import wx.lib.mixins.listctrl as listmix
from wx.lib.agw import ultimatelistctrl as ULC

from endaq.device import (Recorder, getDevices, RECORDERS,
                          deviceChanged, UnsupportedFeature, DeviceError,
                          CommandError, DeviceTimeout)
from endaq.device.base import os_specific
from endaq.device.response_codes import DeviceStatusCode

from .shared import DeviceToolTip
from . import icons
from . import battery_icons
from . import controls
from .events import (EvtDeviceListUpdate, EVT_DEVICE_LIST_UPDATE,
                     EvtRecordButton, EVT_RECORD_BUTTON)

logger = logging.getLogger('endaqconfig')

# ===========================================================================
# Threshold values for showing warning or error icons
# ===========================================================================

# Thresholds for showing device low free space messages, severe and moderate
SPACE_MIN_MB = 16
SPACE_WARN_MB = SPACE_MIN_MB * 4

# Thresholds for showing moderate warnings when device and calibration are
# approaching their expiration dates. If 0 or fewer days remain, a severe
# warning is displayed.
CAL_WARN_DAYS = timedelta(days=120)
DEV_WARN_DAYS = timedelta(days=182)


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


# ===========================================================================
# Column 'formatters.' They actually set the column display and return the
# value for the list sorting (usually the same as the display text, if any).
# Standard arguments are the `Recorder`, the index (row), the column number,
# and the root window/dialog.
# ===========================================================================

def _attribFormatter(attrib: str, 
                     default: str, 
                     dev: Recorder, 
                     index: int, 
                     column: int, 
                     root: "DeviceSelectionDialog") -> str:
    """ Adds a column populated with a Recorder's attribute. Meant to be used
        with `partial()` to supply the first 2 arguments.

        :param attrib: The device's attribute name.
        :param default: The default value to display if the attribute is `None`.
        :param dev: The device beind displayed.
        :param index: The list index (row).
        :param column: The index of the column being populated.
        :param root: The parent window/dialog.
        :return: A string for use in column sorting (same as what's shown).
    """
    val = str(getattr(dev, attrib, default) or '')
    root.list.SetStringItem(index, column, f" {val} ", [])

    return val


def populateButtonColumn(dev: Recorder,
                         index: int,
                         column: int,
                         root: "DeviceSelectionDialog") -> str:
    """ Add a column containing buttons.

        :param dev: The device beind displayed.
        :param index: The list index (row).
        :param column: The index of the column being populated.
        :param root: The parent window/dialog.
        :return: A string for use in column sorting ("" in this case).
    """
    pan = controls.ControlButtons(root, root.list, dev, index, column)
    root.list.SetItemWindow(index, column, pan, expand=True)
    root.minWidths[root.buttonCol] = pan.GetSize()[0]
    return ""


def populateBatteryColumn(dev: Recorder,
                          index: int,
                          column: int,
                          root: "DeviceSelectionDialog") -> str:
    """ Add/update a column containing the battery status icon.

        :param dev: The device beind displayed.
        :param index: The list index (row).
        :param column: The index of the column being populated.
        :param root: The parent window/dialog.
        :return: A string for use in column sorting.
    """
    if column is None:
        return ''

    batIcon, batDesc = 0, ''

    try:
        batStat = root.recorderStatus[dev][0]
        batName, batDesc = battery_icons.batStat2name(batStat)
        batIcon = root.batteryIconIndices.get(batName, 0)
    except KeyError:
        # Probably old, doesn't support getBatteryState()
        pass

    root.list.SetStringItem(index, column, '', batIcon)
    return batDesc


def populateStatusColumn(dev: Recorder,
                         index: int,
                         column: int,
                         root: "DeviceSelectionDialog") -> str:
    """ Add/update a column displaying the device status.

        :param dev: The device beind displayed.
        :param index: The list index (row).
        :param column: The index of the column being populated.
        :param root: The parent window/dialog.
        :return: A string for use in column sorting.
    """
    if column is None:
        return ''

    try:
        code, msg = dev.command.status
    except (AttributeError, UnsupportedFeature):
        code, msg = None, ''

    code = code or DeviceStatusCode.IDLE

    if code is None:
        color = None
        text = None
        code = 1000

    else:
        # Find specific color, or round to lowest multiple of 10
        displayCode = code if code in root.STATUS_COLORS else code // 10
        color = root.STATUS_COLORS.get(displayCode, None)
        text = root.STATUS_TEXT.get(displayCode, "")

        if code < 0:
            color = color or root.STATUS_COLORS.get(-10)
            text = text or root.STATUS_TEXT.get(-10)

    root.list.SetStringItem(index, column, text)

    if not color:
        color = root.list.GetTextColour()

    font = root.list.GetFont()
    item = root.list.GetItem(index, column)
    item.SetMask(ULC.ULC_MASK_FONTCOLOUR | ULC.ULC_MASK_FONT)
    item.SetTextColour(color)
    item.SetFont(font)
    root.list.SetItem(item)

    return code


# ===========================================================================
#
# ===========================================================================

class DeviceSelectionDialog(sc.SizedDialog, listmix.ColumnSorterMixin):
    """ The dialog for selecting a device to configure.
    """

    ID_SET_TIME = wx.NewIdRef()
    ID_START_RECORDING = wx.NewIdRef()

    # Indices of icons. Proportional to severity.
    # Icons after these are battery level, etc.
    ICON_NONE, ICON_INFO, ICON_WARN, ICON_ERROR = range(4)

    # Named tuple to make handling columns slightly cleaner (names vs. indices).
    ColumnInfo = namedtuple("ColumnInfo", ['name',       # Column header text
                                           'formatter',  # To-string function
                                           ])

    # The displayed columns. Each key/value is turned into `ColumnInfo`.
    # TODO: Assemble lists of columns piecemeal based on arguments
    COLUMNS = {
        "Path": partial(_attribFormatter, "path", ""),
        "Name": partial(_attribFormatter, "name", ""),
        "Type": partial(_attribFormatter, "productName", ""),
        "Serial #": partial(_attribFormatter, "serial", ""),
        "Status": populateStatusColumn,
        "Bat.": populateBatteryColumn,
        "Device Control": populateButtonColumn
    }

    ADVANCED_COLUMNS = {
        "Path": partial(_attribFormatter, "path", ""),
        "Name": partial(_attribFormatter, "name", ""),
        "Type": partial(_attribFormatter, "productName", ""),
        "Serial #": partial(_attribFormatter, "serial", ""),
        "Status": populateStatusColumn,
        "HW Rev.": partial(_attribFormatter, "hardwareVersion", ''),
        "FW Rev.": partial(_attribFormatter, "firmware", ''),
        "Bat.": populateBatteryColumn,
        "Device Control": populateButtonColumn,
    }

    # Tool tips for the 'record' button
    RECORD_UNSELECTED = "No recorder selected"
    RECORD_UNSUPPORTED = "Device does not support recording via software"
    RECORD_ENABLED = "Initiate recording on the selected device"

    # Text colors for the Status column
    STATUS_COLORS = {
        0: None,  # Idle
        10: wx.BLUE,  # Recording
        20: wx.YELLOW,  # Reset pending
        30: wx.YELLOW,  # Start Pending
        40: wx.YELLOW,  # Triggering
        50: wx.Colour(200, 200, 200),  # Sleeping
        -10: wx.RED  # Error (default for all negative status codes)
    }

    # Status text
    # DeviceStatusCode seems to get cast to int, so enum names not available
    STATUS_TEXT = {
        0: "Ready",
        10: "Recording",
        20: "Resetting",
        30: "Starting Recording",
        40: "Awaiting Trigger",
        50: "Sleeping",
        -10: "Error"
    }

    # ==============================================================================
    #
    # ==============================================================================


    def GetListCtrl(self):
        # Required by ColumnSorterMixin
        # Is this still required in wxPython >= 4?
        return self.list


    def __init__(self, *args, **kwargs):
        """ Constructor. Takes standard dialog arguments, plus:

            :keyword filter: An optional function to exclude devices from
                the list. It should take a `Recorder` as an argument, and
                return a boolean.
            :keyword autoUpdate: A number of milliseconds to delay between
                checks for changes to attached recorders. 0 will never
                automatically refresh. Default is 500 ms.
            :keyword showWarnings: If `False`, battery age and calibration
                expiration warnings will not be shown for selected devices.
                Default is `True`.
            :keyword showConnection: If `True`, the connection type icon
                (USB, Wi-Fi, Bluetooth) will be shown on the left side of
                each devices' row.
            :keyword showAdvanced: If `True`, show additional columns of
                information (hardware/firmware version, etc.). Default is
                `False`.
            :keyword hideClock: If `True`, the "Set all clocks" button will
                be hidden. Default is `False`.
            :keyword hideRecord: If `True`, the "Start Recording" button
                will be hidden. Default is `False`.
            :keyword okText: Alternate text to display on the OK/Configure
                button. Defaults to `"Configure"`.
            :keyword okHelp: Alternate tooltip for the OK/Configure button.
                Defaults to `"Configure the selected device"`.
            :keyword cancelText: Alternate text to display on the
                Cancel/Close button. Defaults to `"Close"`
            :keyword icon: A `wx.Icon` for the dialog (for platforms that
                support title bar icons). `None` (default) will use the
                package default. `False` will show no icon.
            :keyword tooltips: If `True` (default), show list tooltips
                containing all important device infomation.
            :keyword checks: If `True`, show checkboxes for each device.
            :keyword mustConfig: If `True`, the 'OK' button will only become
                enabled if the device can be configured.
        """
        # Clear cached devices
        RECORDERS.clear()

        style = (wx.DEFAULT_DIALOG_STYLE |
                 wx.RESIZE_BORDER |
                 wx.MAXIMIZE_BOX |
                 wx.MINIMIZE_BOX |
                 wx.DIALOG_EX_CONTEXTHELP |
                 wx.SYSTEM_MENU)

        self.autoUpdate = kwargs.pop('autoUpdate', 500)
        self.hideClock = kwargs.pop('hideClock', False)
        self.hideRecord = kwargs.pop('hideRecord', False)
        self.showWarnings = kwargs.pop('showWarnings', True)
        self.showConnection = kwargs.pop('showConnection', True)
        self.showAdvanced = kwargs.pop('showAdvanced', False)
        self.filter = kwargs.pop('filter', lambda x: True)
        self.checks = kwargs.pop('checks', False)
        self.mustConfigure = kwargs.pop('mustConfig', True)
        okText = kwargs.pop('okText', "Configure")
        okHelp = kwargs.pop('okHelp', 'Configure the selected device')
        cancelText = kwargs.pop('cancelText', "Close")
        icon = kwargs.pop('icon', None)
        tooltips = kwargs.pop('tooltips', True)
        kwargs.setdefault('style', style)

        # Not currently used, but consistent with the main dialog.
        self.DEBUG = kwargs.pop('debug', False)

        sc.SizedDialog.__init__(self, *args, **kwargs)

        if icon is not False:
            icon = icon or icons.icon.GetIcon()
            self.SetIcon(icon)

        self.thread = None  # Device scanning thread
        self.updating = threading.Event()  # Set while updating, so other calls skip.

        # TODO: Better column collection (assemble piecemeal based on parameters)
        cols = self.ADVANCED_COLUMNS if self.showAdvanced else self.COLUMNS
        self.columns = [self.ColumnInfo(name, formatter)
                        for name, formatter in cols.items()]

        pane = self.GetContentsPane()
        pane.SetSizerProps(expand=True)

        self.initList(pane, tooltips)

        # Selected device info
        self.infoText = wx.StaticText(pane, -1, " \n \n \n")
        self.infoText.SetSizerProps(expand=True)
        self.infoText.Show(self.showWarnings)

        buttonpane = sc.SizedPanel(pane, -1)
        buttonpane.SetSizerType("horizontal")
        buttonpane.SetSizerProps(expand=True)

        self.setClockButton = wx.Button(buttonpane, self.ID_SET_TIME,
                                        "Set All Clocks")
        self.setClockButton.SetSizerProps(halign="left")
        self.setClockButton.SetToolTip("Set the time of every attached "
                                       "recorder with a real-time clock")
        self.Bind(wx.EVT_BUTTON, self.OnSetClocks, id=self.ID_SET_TIME)
        self.setClockButton.Show(not self.hideClock)

        self.recordButton = wx.Button(buttonpane, self.ID_START_RECORDING,
                                      "Start Recording")
        self.recordButton.SetSizerProps(halign="left")
        self.recordButton.SetToolTip(self.RECORD_ENABLED)
        self.Bind(wx.EVT_BUTTON, self.OnStartRecording, id=self.ID_START_RECORDING)
        self.recordButton.Enable(False)
        self.recordButton.Show(not self.hideRecord)

        sc.SizedPanel(buttonpane, -1).SetSizerProps(proportion=1)  # Spacer

        self.okButton = wx.Button(buttonpane, wx.ID_OK, okText)
        self.okButton.SetToolTip(okHelp)
        self.okButton.SetSizerProps(halign="right")
        self.okButton.Enable(False)
        self.cancelButton = wx.Button(buttonpane, wx.ID_CANCEL, cancelText)
        self.cancelButton.SetSizerProps(halign="right")

        self.populateList()
        self.Fit()
        self.SetMinSize((640, 300))
        self.SetMaxSize((1500, 600))

        self.Layout()
        self.Centre()

        self.Bind(wx.EVT_SHOW, self.OnShow)
        self.Bind(EVT_RECORD_BUTTON, self.OnStartRecording)
        self.Bind(EVT_DEVICE_LIST_UPDATE, self.OnDeviceListUpdate)


    def initList(self,
                 parent: wx.Panel,
                 tooltips: bool):
        """ Build and set up the device list control.

            :param parent: The parent Panel.
            :param tooltips: Show tooltips if `True`.
        """
        self.batteryCol = None
        self.buttonCol = None
        self.statusCol = None

        for i, col in enumerate(self.columns):
            if col.formatter == populateBatteryColumn:
                self.batteryCol = i
            elif col.formatter == populateButtonColumn:
                self.buttonCol = i
            elif col.formatter == populateStatusColumn:
                self.statusCol = i

        self.recorders = []  # Results of previous `getDevices()`.
        self.recorderStatus = {}  # Recorder status, battery state, and path, keyed by `Recorder`
        self.recordersByIndex = {}  # `Recorder` instances keyed by list index.
        self.indicesByRecorder = {}  # List index keyed by `Recorder`
        # self.recorderBusy = defaultdict(threading.Event)  # Events indicating a recorder is updating, keyed by `Recorder`
        self.selected = None
        self.selectedIdx = None
        self.firstDrawing = True
        self.listWidth = 0

        self.lastUpdate = time()

        self.itemDataMap = {}  # required by ColumnSorterMixin

        self.list = ULC.UltimateListCtrl(parent, -1,
                                         agwStyle=(wx.LC_REPORT
                                                   # | wx.LC_NO_HEADER
                                                   | wx.BORDER_NONE
                                                   | wx.LC_HRULES
                                                   | wx.LC_SINGLE_SEL
                                                   | ULC.ULC_NO_ITEM_DRAG
                                                   # | wx.LC_VRULES
                                                   ))

        self.list.AssignImageList(self.loadIcons(), wx.IMAGE_LIST_SMALL)
        self.list.SetSizerProps(expand=True, proportion=1)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self.list)
        self.list.Bind(wx.EVT_LEFT_DCLICK, self.OnItemDoubleClick)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self.list)

        # For doing per-item tool tips in the list
        self.lastToolTipItem = -1
        self.list.Bind(wx.EVT_MOTION, self.OnListMouseMotion)
        self.list.Bind(wx.EVT_LEAVE_WINDOW, self.OnExitWindow)

        # Manual tool tip generation (ULC tooltips seem broken)
        self.tooltipFrame = DeviceToolTip(self) if tooltips else None

        self.updateTimerCalls = 0

        listmix.ColumnSorterMixin.__init__(self, len(self.columns))


    def loadIcons(self) -> ULC.PyImageList:
        """ Load the list icons (warning indicators and battery level icons)

        :return: An `wx.ImageList` containing the icons.
        """
        images = ULC.PyImageList(16, 16, style=ULC.IL_VARIABLE_SIZE)
        empty = wx.Bitmap(16, 16)
        empty.SetMaskColour(wx.BLACK)
        images.Add(empty)

        # for i in (wx.ART_INFORMATION, wx.ART_WARNING, wx.ART_ERROR):
        #     images.Add(wx.ArtProvider.GetBitmap(i, wx.ART_CMN_DIALOG, (16, 16)))
        for img in icons.STATUS_ICONS:
            images.Add(img.GetBitmap())

        self.batteryIconIndices = {}
        batImages = [item for item in battery_icons.__dict__.items()
                     if item[0].startswith('battery')]

        for i, (name, icon) in enumerate(batImages, images.GetImageCount()):
            self.batteryIconIndices[name] = i
            images.Add(icon.GetBitmap())

        self.ICON_CONNECTION_BT = images.GetImageCount()
        images.Add(icons.connection_bt.GetBitmap())
        self.ICON_CONNECTION_MSD = images.GetImageCount()
        images.Add(icons.connection_msd.GetBitmap())
        self.ICON_CONNECTION_USB = images.GetImageCount()
        images.Add(icons.connection_usb.GetBitmap())
        self.ICON_CONNECTION_WIFI = images.GetImageCount()
        images.Add(icons.connection_wifi.GetBitmap())

        return images


    def getConnectionIcon(self, dev):
        """ Get the index of the appropriate connection type icon.
        """
        if dev.available:
            return self.ICON_CONNECTION_MSD

        # This is a primitive mechanism based on the `ConfigInterface`
        # subclass name. Also, all but USB are currently hypothetical.
        configname = dev.command.__class__.__name__.lower()
        if 'serial' in configname:
            return self.ICON_CONNECTION_USB
        elif 'mqtt' in configname:
            return self.ICON_CONNECTION_WIFI
        elif any(n in configname for n in ('bluetooth', 'bt', 'ble')):
            return self.ICON_CONNECTION_BT
        else:
            return self.ICON_NONE


    def setItemIcon(self, index, dev):
        """ Set the warning icon, message and tool tips for recorders with
            problems.
        """
        # TODO: Refactor this!
        tips = []

        if self.batteryCol is not None:
            bat = self.itemDataMap[index][self.batteryCol]
            if bat:
                tips.append(bat)

        icon = self.ICON_NONE
        now = datetime.now()

        if dev.birthday:
            age = now - dev.birthday
            lifeleft = dev.LIFESPAN - age
        else:
            age = lifeleft = None

        calExp = dev.getCalExpiration()

        pathtext = dev.path
        if dev.path and os.path.exists(dev.path):
            freeSpace = os_specific.getFreeSpace(dev.path) / 1048576
            if freeSpace < SPACE_WARN_MB:
                tip = f"This device is nearly full ({freeSpace:.2f} MB available)."
                icon = self.ICON_INFO
                if freeSpace < SPACE_MIN_MB:
                    tip += " This may prevent configuration."
                    icon = self.ICON_ERROR
                tips.append(tip)
        elif dev.path != 'mqtt':
            # Note: the MQTT API is still in progress. "mqtt" as path may change.
            pathtext = ''

        self.list.SetItemText(index, pathtext or '')

        if lifeleft is not None and lifeleft < DEV_WARN_DAYS:
            icon = max(icon, self.ICON_INFO)
            tips.append(f"This devices is {age.days} days old; battery life may be limited.")
            if lifeleft.days < 0:
                icon = max(icon, self.ICON_WARN)

        if calExp:
            if calExp < now:
                tips.append(f"This device's calibration has expired on {calExp.date()}.")
                icon = max(icon, self.ICON_WARN)
            elif now - calExp < CAL_WARN_DAYS:
                tips.append(f"This device's calibration will expire on {calExp.date()}.")
                icon = max(icon, self.ICON_INFO)

        if self.showConnection:
            self.list.SetItemImage(index, [icon, self.getConnectionIcon(dev)])
        else:
            self.list.SetItemImage(index, [icon])

        if len(tips) == 0:
            self.listToolTips[index] = None
            self.listMsgs[index] = None
            return
        else:
            self.listToolTips[index] = '\n'.join(tips)
            self.listMsgs[index] = '\n'.join([f'\u2022 {s}' for s in tips])


    def createColumns(self):
        """ Add the column headers to the list. Call at the very start
            (before starting the updating thread, so there's an initial
            display) and at the beginning of `populateList()`.
        """
        self.minWidths = []

        for i, c in enumerate(self.columns):
            self.list.InsertColumn(i, c[0])
            if c.name == 'Name':
                width = self.list.GetTextExtent('X' * 25)[0]
            elif c.formatter == populateStatusColumn:
                width = self.list.GetTextExtent('Awaiting Trigger')[0]
            elif i == self.batteryCol:
                width = 40
            else:
                width = self.list.GetTextExtent(c.name)[0]

            self.minWidths.append(width + 4)


    def populateList(self):
        """ Find recorders and add them to the list.
        """
        if self.updating.is_set():
            return

        try:
            logger.debug('populating list')
            self.updating.set()
            self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))

            self.list.ClearAll()
            self.recordersByIndex.clear()
            self.indicesByRecorder.clear()
            self.itemDataMap.clear()
            self.listWidth = 0

            self.createColumns()

            # This is to provide tool tips for individual list rows
            self.listMsgs = [None] * len(self.recorders)
            self.listToolTips = [None] * len(self.recorders)

            for idx, dev in enumerate(self.recorders):
                path = dev.path or ''
                index = self.list.InsertImageStringItem(idx, path, [0], int(self.checks))
                self.itemDataMap[index] = [dev.path]
                self.recordersByIndex[index] = dev
                self.indicesByRecorder[dev] = index
                for i, col in enumerate(self.columns[1:], 1):
                    try:
                        val = col.formatter(dev, index, i, self)  # populates item and returns data map value
                    except (IOError, DeviceError) as err:
                        logger.error(f'Error formatting column {i}: {err!r}')
                        val = None
                    self.itemDataMap[index].append('' if val is None else val)
                    self.list.SetColumnWidth(i, wx.LIST_AUTOSIZE)

                    item = self.list.GetItem(index, i)
                    item.SetMask(ULC.ULC_MASK_FONTCOLOUR | ULC.ULC_MASK_FONT)

                self.list.SetItemData(index, index)

                if self.showWarnings:
                    self.setItemIcon(index, dev)

            for i, w in enumerate(self.minWidths):
                w = w + 8
                if self.list.GetColumnWidth(i) < w:
                    self.list.SetColumnWidth(i, w)
                self.listWidth += self.list.GetColumnWidth(i)

            # if self.batteryCol is not None:
            #     self.list.SetColumnWidth(self.batteryCol, self.minWidths[self.batteryCol])

            if not self.recordersByIndex or not self.selected:
                self.OnItemDeselected(None)

        finally:
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            self.updating.clear()


    def updateRow(self, dev: Recorder, enabled: bool = True):
        """ Update one device (row) in the list.

            :param dev: The device being updated.
            :param enabled:
        """

        if dev not in self.indicesByRecorder:
            # New device, generally shouldn't happen.
            return

        index = self.indicesByRecorder[dev]
        if self.showWarnings:
            self.setItemIcon(index, dev)

        # Status code `None` means device is (temporarily) unavailable
        # (i.e., not present but not yet expired)
        status = self.recorderStatus.get(dev, (None, (DeviceStatusCode.IDLE, '')))[1][0]
        enabled = enabled and status is not None

        # enable or disable the row
        # excludes button panel - do that explicitly
        item = self.list.GetItem(index)
        item.Enable(enabled)
        self.list.SetItem(item)

        for i, col in enumerate(self.columns[1:], 1):
            # Don't rebuild button panel in update
            if i == self.buttonCol:
                val = ''
                pan = self.list.GetItemWindow(index, i)
                if pan:
                    pan.updateButtons(enabled)
                else:
                    logger.error(f'Could not get button panel for index {index}')
            else:
                val = col.formatter(dev, index, i, self)
            self.itemDataMap[index][i] = val or ''


    def updateList(self):
        """ Update the statuses in the displayed list of devices. Called in
            response to a message from the device scanning thread if no
            devices have been added or removed.

            :see: OnDeviceListUpdate()
        """
        # Bail if an update is already being handled
        # (e.g., called from a different thread)
        if self.updating.is_set():
            return

        try:
            self.updating.set()
            # logger.debug('Updating display')
            for dev in self.recorders:
                self.updateRow(dev)

        finally:
            self.updating.clear()


    def getSelected(self) -> Optional[Recorder]:
        """ Get the device corresponding to the selected item in the list.
        """
        if self.selected is None:
            return None
        return self.recordersByIndex.get(self.selected, None)


    def isDead(self) -> bool:
        """ Callback function that indicates the dialog is still working.
            Primarily for use as a callback in threads sending commands
            to devices.
        """
        try:
            if not self.thread or not self.thread.is_alive():
                return True
            return self.thread._cancel.is_set()
        except (AttributeError, RuntimeError) as err:
            # Window probably deleted, and/or app exiting.
            logger.debug(f'Sign-of-life check failed: {err!r}')
            return True


    def enableButtons(self, enabled=True):
        """ Disable/enable main dialog buttons while a command executes.
        """
        butts = self.okButton, self.cancelButton, self.setClockButton
        for b in butts:
            b.Enable(enabled)


    # =======================================================================
    # Event handling
    # =======================================================================

    def OnColClick(self, evt):
        # Required by ColumnSorterMixin
        evt.Skip()


    def OnItemSelected(self, evt):
        """ Handle list item (row) selection.
        """
        self.selected = self.list.GetItemData(evt.Index)
        if self.listMsgs[self.selected] is not None:
            self.infoText.SetLabel(self.listMsgs[self.selected])

        recorder = self.recordersByIndex.get(self.selected, None)
        if not recorder:
            logger.error('Could not get selected recorder!')
            self.okButton.Enable(False)
        if recorder.canRecord:
            self.recordButton.SetToolTip(self.RECORD_ENABLED)
            self.recordButton.Enable(True)
        else:
            self.recordButton.SetToolTip(self.RECORD_UNSUPPORTED)
            self.recordButton.Enable(False)

        try:
            if not self.mustConfigure:
                en = True
            else:
                en = recorder.hasConfigInterface and recorder.config.available
            self.okButton.Enable(en)
        except AttributeError as err:
            logger.debug(f'Ignoring error checking device configurablity: {err!r}')
            self.okButton.Enable(not self.mustConfigure)

        evt.Skip()


    def OnItemDeselected(self, evt):
        """ Handle list item (row) deselection.
        """
        self.selected = None
        self.okButton.Enable(False)
        if self.showWarnings:
            self.infoText.SetLabel("\n")
        else:
            self.infoText.SetLabel("")

        self.recordButton.Enable(False)
        self.recordButton.SetToolTip(self.RECORD_UNSELECTED)

        if evt is not None:
            evt.Skip()


    def OnItemDoubleClick(self, evt):
        """ Hande lsit item (row) double-click.
        """
        if self.list.GetSelectedItemCount() > 0:
            # Close the dialog
            self.EndModal(wx.ID_OK)
        evt.Skip()


    def OnListMouseMotion(self, evt):
        """ Handle mouse movement, updating the tool tips, etc.
            This determines the list item under the mouse and shows the
            appropriate tool tip, if any
        """
        if not self.recordersByIndex or not self.tooltipFrame:
            evt.Skip()
            return

        # Part of workaround for broken ULC tooltips. It can probably be removed
        # if/when ULC tooltips get fixed.
        self.tooltipFrame.timer.Stop()
        self.tooltipFrame.Hide()

        index, _ = self.list.HitTest(evt.GetPosition())
        if index != wx.NOT_FOUND:
            if index != self.lastToolTipItem:
                item = self.list.GetItemData(index)
                text = self.listToolTips[item]

                # Everything here on is part of ULC tooltip workaround.
                self.tooltipFrame.setText(text)
                self.lastToolTipItem = index
            if not self.tooltipFrame.IsShown():
                self.tooltipFrame.timer.StartOnce(self.tooltipFrame.TOOLTIP_TIME)

        evt.Skip()


    def OnExitWindow(self, evt):
        """ Handle the mouse leaving the window. """
        if self.tooltipFrame:
            self.tooltipFrame.timer.Stop()
            self.tooltipFrame.Hide()
        evt.Skip()


    def OnShow(self, evt):
        """ Handle dialog being shown/hidden.
        """
        if evt.IsShown():
            if self.autoUpdate:
                if not self.thread or not self.thread.is_alive():
                    self.thread = DeviceScanThread(self, self.filter, self.autoUpdate)
                    self.thread.start()
        else:
            if self.thread and self.thread.is_alive():
                self.thread.stop()
            if self.tooltipFrame:
                self.tooltipFrame.timer.Stop()
                self.tooltipFrame.Hide()
        evt.Skip()
        

    def OnSetClocks(self, _evt=None):
        """ Set all clocks. Used as an event handler.
        """
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        self.enableButtons(False)

        try:
            if self.thread and self.thread.is_alive():
                self.thread.pause()

            deadline = time() + 5
            threads = [DeviceCommandThread(rec, rec.setTime)
                       for rec in self.recordersByIndex.values()]

            while any(t.is_alive() for t in threads):
                if time() > deadline:
                    break
                sleep(0.05)

            fails = []
            for t in threads:
                rec = t.device
                name = f"{rec.productName} SN:{rec.serial}"
                if t.failed.is_set():
                    logger.error(f"Error setting clock on {rec}: {t.failure!r}")
                    fails.append(name)
                elif not t.completed.is_set():
                    logger.error(f"Timed out setting clock on {rec}")
                    fails.append(f"{name} (timed out)")

            if fails:
                if len(fails) > 1:
                    names = "\u2022 " + ('\n\u2022 '.join(fails))
                    msg = ("Could not set recorder clocks.\n\n"
                           "Errors prevented the clocks being set on these recorders:\n\n"
                           f"{names}")
                else:
                    msg = ("Could not set recorder clock.\n\n"
                           "An error prevented the clock from being set on "
                           f"recorder {fails[0]}.")

                wx.MessageBox(msg, "Device Error", parent=self,
                              style=wx.OK | wx.ICON_ERROR)

        finally:
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            self.enableButtons(True)

            if self.thread and self.thread.is_alive():
                self.thread.resume()


    def OnStartRecording(self,
                         evt: Union[wx.CommandEvent, EvtRecordButton, None] = None):
        """ Initiate a recording.

            :param evt: The event generated by a dialog 'Record' button, or
                an `EVT_RECORD_BUTTON` event from a row in the list.
        """
        if self.thread and self.thread.is_alive():
            self.thread.pause()

        try:
            # If EVT_RECORD_BUTTON, get device from event, otherwise use selected
            recorder = getattr(evt, 'device', None)
            stop = getattr(evt, 'stop', False)
            if not recorder:
                recorder = self.recordersByIndex.get(self.selected, None)
            if recorder and recorder.canRecord:
                self.updateRow(recorder, enabled=False)
                if stop:
                    # recorder.command.stopRecording()
                    DeviceCommandThread(recorder, recorder.command.stopRecording,
                                        callback=self.isDead)
                else:
                    # recorder.command.startRecording()
                    DeviceCommandThread(recorder, recorder.command.startRecording,
                                        callback=self.isDead)
        finally:
            if self.thread and self.thread.is_alive():
                self.thread.resume()


    def OnDeviceListUpdate(self, evt):
        """ Handle an event generated by the thread scanning for new and
            changed devices.
        """
        now = time()
        new = evt.devices
        stat = evt.status
        devicesChanged = new != self.recorders
        statsChanged = stat != self.recorderStatus

        self.recorders = new
        self.recorderStatus = stat

        if devicesChanged:
            self.populateList()
        elif statsChanged or now - self.lastUpdate > 10:
            # Same devices, different status (or time to force an update,
            # making sure nothing in the list has gotten 'stuck')
            self.lastUpdate = now
            self.updateList()

        if  self.updateTimerCalls == 0:
            # First update; resize to fit list contents
            logger.debug('first update')
            self.SetSize((self.listWidth + (self.GetDialogBorder() * 4), -1))
            # self.list.Fit()
            # self.Centre()

        self.updateTimerCalls += 1


# ===========================================================================
#
# ===========================================================================

def selectDevice(title: str = "Select Recorder",
                 parent: Optional[wx.Window] = None,
                 **kwargs):
    """ Display a device-selection dialog and return the path to a recorder.
        The dialog will (optionally) update automatically when devices are
        added or removed.

        :param title: A title string for the dialog.
        :param parent: The parent window, if any.
        :keyword filter: An optional function to exclude devices from the
            list. It should take a `Recorder` as an argument, and return a
            boolean.
        :keyword autoUpdate: A number of milliseconds to delay between checks
            for changes to attached recorders. 0 will never automatically
            refresh. Default is 500 ms.
        :keyword showWarnings: If `False`, battery age and calibration
            expiration warnings will not be shown for selected devices.
            Default is `True`.
        :keyword showAdvanced: If `True`, show additional columns of
            information (hardware/firmware version, etc.). Default is `False`.
        :keyword hideClock: If `True`, the "Set all clocks" button will be
            hidden. Default is `False`.
        :keyword hideRecord: If `True`, the "Start Recording" button will be
            hidden. Default is `False`.
        :keyword okText: Alternate text to display on the OK/Configure button.
            Defaults to `"Configure"`.
        :keyword okHelp: Alternate tooltip for the OK/Configure button.
            Defaults to `"Configure the selected device"`.
        :keyword cancelText: Alternate text to display on the Cancel/Close
            button. Defaults to `"Close"`
        :keyword icon: A `wx.Icon` for the dialog (for platforms that support
            title bar icons). `None` (default) will use the package default.
            `False` will show no icon.
        :keyword tooltips: If `True` (default), show list tooltips containing
            all important device infomation.
        :return: The path of the selected device.
    """
    result = None

    dlg = DeviceSelectionDialog(parent, -1, title, **kwargs)

    if dlg.ShowModal() == wx.ID_OK:
        result = dlg.getSelected()

    dlg.Destroy()
    if isinstance(result, dict):
        result = result.get('_PATH', None)
    return result
