"""
Dialog for selecting and/or controlling recording devices.

TODO: Broker selection cosmetics
TODO: Automatic connect to a default broker (if provided on init and 'use remote' starts checked)
TODO: Automatically connect to the first broker found (if no default and 'use remote' starts checked)
"""

from collections import namedtuple
import datetime
from functools import partial
import logging
import os.path
import threading
from time import sleep, time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import wx
import wx.lib.sized_controls as sc
import wx.lib.mixins.listctrl as listmix
from wx.lib.agw import ultimatelistctrl as ULC
import wx.lib.filebrowsebutton as FBB

from endaq.device import (Recorder, RECORDERS, UnsupportedFeature,
                          CommandError, DeviceError, deviceChanged,
                          _module_busy)
from endaq.device.base import os_specific
from endaq.device.mqtt.mqtt_interface import MQTTCommandInterface, MQTTConnector

from endaqconfig.common import isGateway, isOnline, isSleeping
from endaqconfig.widgets import battery_icons
from endaqconfig.widgets import icons
from endaqconfig.widgets.broker_dialog import BrokerDialog
from endaqconfig.widgets.controls import (
    _attribFormatter, populateStatusColumn, populateButtonColumn,
    populateBatteryColumn, NewControlButtons, ListContextMenu,
    STATUS_DISPLAY)
from endaqconfig.widgets.events import (
    EVT_RECORD, EVT_STREAM, EVT_CONFIG, EVT_LOCK_DEVICE, EVT_BLINK,
    EVT_BROKER_SELECTED, EVT_MQTT_CONNECTING, EVT_MQTT_CONNECTED,
    EVT_MQTT_DISCONNECTED, EVT_MQTT_ERROR, EVT_RESET, EVT_SHUTDOWN,
    EvtMQTTError)
from endaqconfig.widgets.threads import (DeviceScanThread, DeviceCommandThread, BrokerConnectThread)
from endaqconfig.widgets.shared import DeviceToolTip, promptDeviceReboot, promptDeviceShutdown

logger = logging.getLogger(__name__)

import endaq.device
endaq.device.logger.setLevel(logging.DEBUG)

# ===========================================================================
# Threshold values for showing warning or error icons
# ===========================================================================

# Thresholds for showing device low free space messages, severe and moderate
SPACE_MIN_MB = 16
SPACE_WARN_MB = SPACE_MIN_MB * 4

# Thresholds for showing moderate warnings when device and calibration are
# approaching their expiration dates. If 0 or fewer days remain, a severe
# warning is displayed.
CAL_WARN_DAYS = datetime.timedelta(days=120)
DEV_WARN_DAYS = datetime.timedelta(days=182)

DEFAULT_BROKER = "DRS Test Broker"  # TODO: REMOVE/CHANGE

DISCONNECT_TIMEOUT = 10
CONNECT_FAIL_TIMEOUT = 30


# ===========================================================================
#
# ===========================================================================

class DeviceSelectionDialog(sc.SizedDialog, listmix.ColumnSorterMixin):
    """ The dialog for selecting a device to configure.
    """

    ID_SET_TIME = wx.NewIdRef()
    ID_START_RECORDING = wx.NewIdRef()

    # Indices of icons in the `PyImageList`. Proportional to severity.
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
    RECORD_ENABLED = "Initiate recording on all capable devices"

    SERIAL_TIMEOUT = 10
    MQTT_TIMEOUT = 125


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
            :keyword scanInterval: The number of milliseconds between
                scans for new devices. Default is 4000 ms.
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
            :keyword allowDoubleClick: If `True`, double-clicking a list item
                will be the same as selecting it and clicking OK. Defaults
                to `False` if `checks` is `True`.
            :keyword mustConfig: If `True`, the 'OK' button will only become
                enabled if the device can be configured.
            :keyword remote: If `True`, show the MQTT broker selection field.
            :keyword remoteChecked: The initial state of the 'use remote'
                checkbox, if `remote` is `True`. `True` by default.
            :keyword broker: The name of the default, initially selected
                broker. `None` will select the first found.
            :keyword connector: An existing `endaq.device.mqtt.MQTTConnector`
                instance, if one was already created.
            :keyword showSave: If `True`, show the save path selector.
            :keyword savePath: The default save path for streams.

        """
        # Clear cached devices
        RECORDERS.clear()

        self.autoUpdate: Union[int, bool] = kwargs.pop('autoUpdate', 750)
        self.scanInterval: Union[int, bool] = kwargs.pop('scanInterval', 4000)
        self.hideClock: bool = kwargs.pop('hideClock', False)
        self.hideRecord: bool = kwargs.pop('hideRecord', True)
        self.showWarnings: bool = kwargs.pop('showWarnings', True)
        self.showConnection: bool = kwargs.pop('showConnection', True)
        self.showAdvanced: bool = kwargs.pop('showAdvanced', False)
        self.filter: Callable = kwargs.pop('filter', lambda x: True)
        self.checks: bool = kwargs.pop('checks', True)
        self.allowDoubleClick: bool = kwargs.pop('allowDoubleClick', not self.checks)
        self.mustConfigure: bool = kwargs.pop('mustConfig', True)
        self.remote: bool = kwargs.pop('remote', True)
        self.remoteChecked: bool = kwargs.pop('remoteChecked', self.remote)
        self.showSave: bool = kwargs.pop('showSave', True)
        self.savePath: str = kwargs.pop('savePath', '')
        self.connector: MQTTConnector = kwargs.pop('connector', None)

        self.ownConnector = self.connector is not None
        self.oldUpdateCallback = None

        self.defaultBroker: Optional[str] = kwargs.pop('broker', DEFAULT_BROKER)
        okText = kwargs.pop('okText', "Configure")
        okHelp = kwargs.pop('okHelp', 'Configure the selected device')
        cancelText = kwargs.pop('cancelText', "Close")
        icon = kwargs.pop('icon', None)
        tooltips = kwargs.pop('tooltips', True)
        kwargs.setdefault('style', (wx.DEFAULT_DIALOG_STYLE
                                    | wx.RESIZE_BORDER
                                    | wx.MAXIMIZE_BOX
                                    | wx.MINIMIZE_BOX
                                    | wx.DIALOG_EX_CONTEXTHELP
                                    | wx.SYSTEM_MENU
                                    ))

        # Not currently used, but consistent with the main dialog.
        self.DEBUG = kwargs.pop('debug', False)

        sc.SizedDialog.__init__(self, *args, **kwargs)

        icon = icon or icons.icon.GetIcon()
        self.SetIcon(icon)

        self.updateTimer = wx.Timer(self)
        self.updateCount: int = 0
        self.updateCancelled = threading.Event()  # Use as callback for getBatteryStatus/ping commands
        self.scanThread: DeviceScanThread = None

        self.disconnectTimer = wx.Timer(self)  # Timer to remove MQTT devices after disconnection
        self.connectFailTimer = wx.Timer(self)  # Failsafe to re-enable broker selection if connect thread fails

        self.updatingDisplay = threading.Event()  # Set while updating, so other calls skip.
        self.menuOpen = threading.Event()  # Set while context menu open, preventing list updates.

        self.recorders: List[Recorder] = []  # The currently-displayed recorders.
        self.recorderStatus: Dict[Recorder, Tuple] = {}  # Recorder status, battery state, and path, keyed by `Recorder`
        self.recorderTimeouts: Dict[Recorder, float] = {}  # Time to remove a recorder from `recorderStatus` if not in `getDevices()`
        self.recordersByIndex: Dict[int, Recorder] = {}  # `Recorder` instances keyed by list index.
        self.indicesByRecorder: Dict[Recorder, int] = {}  # List index keyed by `Recorder`
        self.checkedRecorders: set[Recorder] = set()  # Checked items/recorders (to keep checks after list updates)

        self.brokerInfo: Optional[dict] = None  # Selected MQTT broker's mDNS info

        # TODO: Better column collection (assemble piecemeal based on parameters)
        cols = self.ADVANCED_COLUMNS if self.showAdvanced else self.COLUMNS
        self.columns = [self.ColumnInfo(name, formatter)
                        for name, formatter in cols.items()]

        pane = self.GetContentsPane()
        pane.SetSizerProps(expand=True)

        self.initList(pane, tooltips)

        if self.checks:
            self._addSelectButtons(pane)

        # Selected device info
        self.infoText = wx.StaticText(pane, -1, " \n \n \n")
        # noinspection PyUnresolvedReferences
        self.infoText.SetSizerProps(expand=True)
        self.infoText.Show(self.showWarnings)

        self.textColorNormal = self.infoText.GetForegroundColour()
        self.textColorError = wx.RED

        if self.remote is not None:
            self._addBrokerSelect(pane)

        # if self.showSave:
        #     self._addStreamTo(pane, default=self.savePath)

        self._addButtons(pane, okText, okHelp, cancelText)

        self.populateList()
        self.Fit()
        self.SetMinSize((640, 300))
        self.SetMaxSize((1500, 600))
        self.SetSize((640, 440 if self.checks else 300))

        self.Layout()
        self.Centre()

        self.Bind(wx.EVT_SHOW, self.OnShow)
        self.Bind(EVT_RECORD, self.OnStartRecording)
        self.Bind(EVT_STREAM, self.OnStartStreaming)
        self.Bind(EVT_CONFIG, self.OnConfigButton)
        self.Bind(EVT_BLINK, self.OnBlink)
        self.Bind(EVT_LOCK_DEVICE, self.OnLockDevice)
        self.Bind(EVT_RESET, self.OnRebootDevice)
        self.Bind(EVT_SHUTDOWN, self.OnShutdownDevice)

        self.Bind(wx.EVT_TIMER, self.OnUpdateTimerTick, id=self.updateTimer.GetId())
        self.Bind(wx.EVT_TIMER, self.OnConnectFailTimer, id=self.connectFailTimer.GetId())
        self.Bind(wx.EVT_TIMER, self.OnDisconnectTimer, id=self.disconnectTimer.GetId())


    # TODO: REMOVE NEXT COMMENT LATER (linter doesn't like monkeypatched sizer methods, clutters everything up)
    # xnoinspection PyUnresolvedReferences
    def _addBrokerSelect(self, pane):
        """ Add MQTT Broker selection widgets.
        """
        selpane = self.brokerPane = sc.SizedPanel(pane, -1)
        selpane.SetSizerType("horizontal")
        selpane.SetSizerProps(expand=True)
        self.remoteCheck = wx.CheckBox(selpane, -1, "Show Remote Devices")
        self.remoteCheck.SetSizerProps(valign='centre')

        self.brokerLabel = wx.StaticText(selpane, -1, "Broker:")
        self.brokerLabel.SetSizerProps(valign='centre', border=(['top', 'left'], 2))
        self.brokerNameField = wx.TextCtrl(selpane, style=wx.TE_READONLY)
        self.brokerNameField.SetSizerProps(expand=True, proportion=1)
        self.brokerSelectBtn = wx.Button(selpane, -1, "Select...")
        self.brokerSelectBtn.SetSizerProps(valign='centre', border=(['right'], 16))
        self.brokerMessageText = wx.StaticText(selpane, -1, ' '*40, style=wx.ST_ELLIPSIZE_END)
        self.brokerMessageText.SetSizerProps(expand=True, proportion=1, valign='centre',
                                             border=(['top'], 2))

        self.remoteCheck.Bind(wx.EVT_CHECKBOX, self.OnRemoteCheckChanged)
        self.brokerSelectBtn.Bind(wx.EVT_BUTTON, self.OnBrokerSelect)
        self.Bind(EVT_BROKER_SELECTED, self.OnBrokerSelected)
        self.Bind(EVT_MQTT_CONNECTING, self.OnMQTTConnecting)
        self.Bind(EVT_MQTT_CONNECTED, self.OnMQTTConnected)
        self.Bind(EVT_MQTT_DISCONNECTED, self.OnMQTTDisconnected)
        self.Bind(EVT_MQTT_ERROR, self.OnMQTTError)


    def showBrokerSelection(self, show=True):
        """ Show or hide the broker name/button/etc.
        """
        self.brokerLabel.Enable(show)
        self.brokerNameField.Enable(show)
        self.brokerSelectBtn.Enable(show)
        self.brokerMessageText.Enable(show)
        # self.brokerLabel.Show(show)
        # self.brokerNameField.Show(show)
        # self.brokerSelectBtn.Show(show)
        # self.brokerMessageText.Show(show)


    # TODO: REMOVE NEXT LINE LATER (linter doesn't like monkeypatched sizer methods, clutters everything up)
    # noinspection PyUnresolvedReferences
    def _addSelectButtons(self, pane, defaultPath=''):
        """ Add buttons for selecting and controlling selected items.
        """
        NewControlButtons._loadImages()
        startIcons = NewControlButtons.ICONS[1]
        stopIcons = NewControlButtons.ICONS[2]
        streamIcons = NewControlButtons.ICONS[3]

        buttonpane = sc.SizedPanel(pane, -1)
        buttonpane.SetSizerType("horizontal")
        buttonpane.SetSizerProps(expand=True)

        def _add(label, icons, tooltip, handler):
            """ Helper to do the button-adding busy work. """
            btn = wx.Button(buttonpane, -1, label)
            btn.SetBitmap(icons[0], wx.LEFT)
            btn.SetBitmapCurrent(icons[1])
            btn.SetBitmapPressed(icons[2])
            btn.SetBitmapDisabled(icons[3])
            btn.SetBitmapMargins((0, 0))
            btn.SetToolTip(tooltip)
            btn.Enable(False)
            btn.Bind(wx.EVT_BUTTON, handler)
            return btn

        self.selectAllBtn = wx.BitmapButton(buttonpane, -1, icons.select_all.GetBitmap())
        self.selectAllBtn.SetToolTip('Check All')
        self.selectNoneBtn = wx.BitmapButton(buttonpane, -1, icons.select_none.GetBitmap())
        self.selectNoneBtn.SetToolTip('Check None')

        self.multiStartBtn = _add('Start Checked', startIcons,
                                  "Send the start recording command to all checked devices",
                                  self.OnStartSelected)
        self.multiStreamBtn = _add('Stream from Checked', streamIcons,
                                   "Send the start command to all checked devices, "
                                   "saving output to the specified directory",
                                   self.OnStreamSelected)
        self.multiStopBtn = _add('Stop Checked', stopIcons,
                                   "Send the stop command to all checked devices",
                                   self.OnStopSelected)

        self.savePathField = FBB.DirBrowseButton(buttonpane,
                                                 labelText="Save to:",
                                                 initialValue=defaultPath,
                                                 changeCallback=self.OnSavePathPicked)
        self.savePathField.SetSizerProps(valign='center', expand=True, proportion=1)

        # Note: setting the width of the all/none buttons wasn't taking for some reason.
        #  The `SetBitmapMargins` fixes it, but may have cosmetic issues on different
        #  platforms and/or screen resolutions.
        h = self.multiStreamBtn.GetSize().height
        size = wx.Size(h, h)
        self.selectAllBtn.SetSize(size)
        self.selectAllBtn.SetBitmapMargins((4, 2))
        self.selectNoneBtn.SetSize(size)
        self.selectNoneBtn.SetBitmapMargins((4, 2))

        self.Bind(wx.EVT_BUTTON, self.OnSelectAllButton, self.selectAllBtn)
        self.Bind(wx.EVT_BUTTON, self.OnSelectNoneButton, self.selectNoneBtn)


    # TODO: REMOVE NEXT LINE LATER (linter doesn't like monkeypatched sizer methods, clutters everything up)
    # noinspection PyUnresolvedReferences
    def _addButtons(self, pane, okText, okHelp, cancelText):
        """ Add device selection dialog bottom buttons.
        """
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
                                      "Start All Recorders")
        self.recordButton.SetSizerProps(halign="left")
        self.recordButton.SetToolTip(self.RECORD_ENABLED)
        self.Bind(wx.EVT_BUTTON, self.OnStartAllRecorders, id=self.ID_START_RECORDING)
        self.recordButton.Enable(False)
        self.recordButton.Show(not self.hideRecord)

        sc.SizedPanel(buttonpane, -1).SetSizerProps(proportion=1)  # Spacer

        self.okButton = wx.Button(buttonpane, wx.ID_OK, okText)
        self.okButton.SetToolTip(okHelp)
        self.okButton.SetSizerProps(halign="right")
        self.okButton.Enable(False)
        self.cancelButton = wx.Button(buttonpane, wx.ID_CANCEL, cancelText)
        self.cancelButton.SetSizerProps(halign="right")


    # TODO: REMOVE NEXT LINE LATER (linter doesn't like monkeypatched sizer methods, clutters everything up)
    # noinspection PyUnresolvedReferences
    def initList(self,
                 parent: wx.Panel,
                 tooltips: bool):
        """ Build and set up the device list control.

            :param parent: The parent Panel.
            :param tooltips: Show tooltips if `True`.
        """
        self.listToolTips: list[str] = []
        self.batteryCol: int = None
        self.buttonCol: int = None
        self.statusCol: int = None

        for i, col in enumerate(self.columns):
            if col.formatter == populateBatteryColumn:
                self.batteryCol = i
            elif col.formatter == populateButtonColumn:
                self.buttonCol = i
            elif col.formatter == populateStatusColumn:
                self.statusCol = i

        self.selected = None
        self.selectedIdx = None
        self.firstDrawing = True
        self.listWidth = 0

        self.lastUpdate = time()

        self.itemDataMap = {}  # required by ColumnSorterMixin

        self.list = ULC.UltimateListCtrl(parent, -1,
                                         agwStyle=(wx.LC_REPORT
                                                   | wx.BORDER_NONE
                                                   | wx.LC_HRULES
                                                   | wx.LC_SINGLE_SEL
                                                   | ULC.ULC_NO_ITEM_DRAG
                                                   # | wx.LC_VRULES
                                                   | ULC.ULC_HOT_TRACKING
                                                   # | ULC.ULC_BORDER_SELECT
                                                   ))

        self.list.AssignImageList(self.loadIcons(), wx.IMAGE_LIST_SMALL)
        self.list.SetSizerProps(expand=True, proportion=1)
        self.defaultColor = self.list.GetForegroundColour()
        self.defaultFont = self.list.GetFont()
        self.sleepingListFont = self.defaultFont.Italic()
        self.boldListFont = self.defaultFont.Bold()

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self.list)
        self.list.Bind(wx.EVT_LEFT_DCLICK, self.OnItemDoubleClick)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self.list)
        self.list.Bind(wx.EVT_RIGHT_DOWN, self.OnListRightClick)

        if self.checks:
            self.Bind(ULC.EVT_LIST_ITEM_CHECKED, self.OnItemChecked, self.list)

        # For doing per-item tool tips in the list
        self.lastToolTipItem = -1
        self.list.Bind(wx.EVT_MOTION, self.OnListMouseMotion)
        self.list.Bind(wx.EVT_LEAVE_WINDOW, self.OnExitWindow)

        # Manual tool tip generation (ULC tooltips seem broken)
        self.tooltipFrame = DeviceToolTip(self) if tooltips else None

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
        batImages = [item for item in vars(battery_icons).items()
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
            # Mounted as a drive
            return self.ICON_CONNECTION_MSD

        # TODO: Special-case icon for Gateway
        try:
            # This is a primitive mechanism based on the `ConfigInterface`
            # subclass name. Also, all but USB are currently hypothetical.
            configname = dev.command.__class__.__name__.lower()
            if 'serial' in configname:
                return self.ICON_CONNECTION_USB
            elif 'mqtt' in configname:
                return self.ICON_CONNECTION_WIFI
            elif any(n in configname for n in ('bluetooth', 'bt', 'ble')):
                # For future use
                return self.ICON_CONNECTION_BT
        except (AttributeError, NotImplementedError, UnsupportedFeature):
            pass

        return self.ICON_NONE


    def setItemIcon(self, index, dev):
        """ Set the warning icon, message and tool tips for recorders with
            problems.
        """
        # TODO: Refactor this!
        tips = []
        bat = ''

        if self.batteryCol is not None:
            bat = self.itemDataMap[index][self.batteryCol]
            if bat:
                bat += '\n'

        icon = self.ICON_NONE

        now = datetime.datetime.now(datetime.timezone.utc)

        if dev.birthday:
            # HACK: datetime values differed at least 3 times between Python
            #  versions 3.9 and 3.12+; make explicitly sure we're using UTC.
            age = now - dev.birthday.replace(tzinfo=datetime.timezone.utc)
            lifeleft = dev.LIFESPAN - age
        else:
            age = lifeleft = None

        pathtext = dev.path
        if dev.path and os.path.exists(dev.path):
            freeSpace = os_specific.getFreeSpace(dev.path) / 1048576
            if freeSpace < SPACE_WARN_MB:
                tip = f"⚠ This device is nearly full ({freeSpace:.2f} MB available)."
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
            if lifeleft.days > 0:
                tips.append(f"🛈 This devices is {age.days} days old; battery life may be limited.")
            else:
                tips.append(f"⚠ This devices is {age.days} days old; battery life may be significantly limited.")
                icon = max(icon, self.ICON_WARN)

        # Check for cached cal data, skip if not present. As it can be slow
        # on MQTT devices (endaq.device circa 2025-09), reading this is done
        # in a separate thread.
        if dev._calibration:
            calExp = dev.getCalExpiration()
            if calExp:
                calExp = calExp.replace(tzinfo=datetime.timezone.utc)
                if calExp < now:
                    tips.append(f"⚠ This device's calibration has expired on {calExp.date()}.")
                    icon = max(icon, self.ICON_WARN)
                elif now - calExp < CAL_WARN_DAYS:
                    tips.append(f"🛈 This device's calibration will expire on {calExp.date()}.")
                    icon = max(icon, self.ICON_INFO)

        if self.showConnection:
            self.list.SetItemImage(index, [icon, self.getConnectionIcon(dev)])
        else:
            self.list.SetItemImage(index, [icon])

        tips.insert(0, bat)
        # Popup tool tips show battery status and each message on its own
        # line. In-dialog help message under list shows battery on one,
        # all other messages on the other.
        self.listMsgs[index] = ' '.join(tips)
        self.listToolTips[index] = '\n'.join(tips)


    def createColumns(self):
        """ Add the column headers to the list. Call at the very start
            (before starting the updating thread, so there's an initial
            display) and at the beginning of `populateList()`.
        """
        # NOTE: 1st column width way too narrow for Linux/macOS device paths!
        #  Maybe just let it truncate in display by default; it usually isn't
        #  critical info, and the user can resize the columns.
        self.minWidths = []

        start = 0
        cols = self.columns

        for i, c in enumerate(cols, start):
            self.list.InsertColumn(i, c[0])
            if c.name == 'Path' and self.checks:
                width = 50
            elif c.name == 'Name':
                width = self.list.GetTextExtent('W' * 20)[0]
            elif c.formatter == populateStatusColumn:
                width = self.list.GetTextExtent('Awaiting Trigger')[0]
            elif i == self.batteryCol:
                width = 40
            elif c.name == 'Type':
                width = self.list.GetTextExtent('W8-R5000D40')[0] + 16
            else:
                width = self.list.GetTextExtent(c.name)[0]

            self.minWidths.append(width + 4)


    def populateList(self):
        """ Find recorders and add them to the list.
        """
        try:
            logger.debug('populating list')
            self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))

            # Get checked devices (may have different list indices)
            checked = self.checkedRecorders.copy()

            self.list.ClearAll()
            self.recordersByIndex.clear()
            self.indicesByRecorder.clear()
            self.checkedRecorders.clear()
            self.itemDataMap.clear()
            self.listWidth = 0

            self.createColumns()

            # This is to provide tool tips for individual list rows
            self.listMsgs = [None] * len(self.recorders)
            self.listToolTips = [None] * len(self.recorders)

            for idx, dev in enumerate(self.recorders):
                path = dev.path or ''
                index = self.list.InsertImageStringItem(idx, path, [0], int(self.checks))
                self.list.EnableItem(index, enable=isOnline(dev))
                # print(f'{dev} {dev.command.status} {isOnline(dev)=} {isSleeping(dev)=}')

                # update dict of checked recorders with new list indices
                if dev in checked:
                    self.checkedRecorders.add(dev)

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

                self.updateRow(dev)

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
            logger.debug('populating list complete')


    def updateRow(self, dev: Recorder, enabled: bool = True):
        """ Update one device (row) in the list.

            :param dev: The device being updated.
            :param enabled: Use `False` to force a device to appear disabled.
        """

        if dev not in self.indicesByRecorder:
            # New device, generally shouldn't happen.
            return

        index = self.indicesByRecorder[dev]
        if self.showWarnings:
            self.setItemIcon(index, dev)

        # try:
        #     status = self.recorderStatus[dev][1][0]
        # except (KeyError, IndexError) as err:
        #     logger.debug(f'recorder status error: {err!r}')
        #     status = 0

        lockId = dev.command.lockId[1]
        locked = lockId and any(lockId)
        mine = lockId == dev.command.hostId
        anothers = locked and not mine
        enabled = (enabled and isOnline(dev) and not anothers)
        sleeping = isSleeping(dev)

        # enable or disable the row
        # excludes button panel - do that explicitly
        item = self.list.GetItem(index)
        item.Enable(enabled)
        item.Check(dev in self.checkedRecorders)
        self.list.SetItem(item)

        font = self.defaultFont
        color = self.defaultColor

        if sleeping:
            # Sleeping/periodically online devices not disabled, but
            # drawn in gray as if they were (so checkbox still accessible)
            color = STATUS_DISPLAY[100][1]
            font = self.sleepingListFont
        elif isGateway(dev):
            # DCB/HDS Gateway device; highlight it.
            font = self.boldListFont

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

            self.list.SetItemTextColour(index, color)
            self.list.SetItemFont(index, font)
            self.itemDataMap[index][i] = val or ''


    def updateList(self, skip: bool = True):
        """ Update the statuses in the displayed list of devices. Called in
            response to a message from the device scanning thread if no
            devices have been added or removed.

            :see: OnDeviceListUpdate()

            :param skip: If `True` and `updatingDisplay` is set, return
                immediately. If `False`, ignore `updatingDisplay`.
        """
        # Bail (not block) if an update is already being handled
        # (e.g., called from a different thread)
        if skip and self.updatingDisplay.is_set():
            logger.debug('Bailing on updateList - updatingDisplay is set')
            return

        # logger.debug('entered updateList')
        for dev in self.recorders:
            try:
                self.updateRow(dev)
            except IndexError:
                # Possible error in row population, or race condition
                logger.debug(f'IndexError updating row for device {dev.serial}')

        checked = self.list.GetCheckedItemCount() > 0
        self.multiStreamBtn.Enable(checked)
        self.multiStartBtn.Enable(checked)
        self.multiStopBtn.Enable(checked)


    def getSelected(self) -> Optional[Recorder]:
        """ Get the device corresponding to the selected item in the list.
        """
        if self.selected is None:
            return None
        return self.recordersByIndex.get(self.selected, None)


    def enableButtons(self, enabled=True):
        """ Disable/enable main dialog buttons while a command executes.
        """
        butts = self.okButton, self.cancelButton, self.setClockButton
        for b in butts:
            b.Enable(enabled)


    def startUpdater(self):
        """ Start the display updating threads and timers.
        """
        if not self.scanThreadRunning():
            interval = self.scanInterval / 1000 if self.autoUpdate else 0
            self.scanThread = DeviceScanThread(self, interval)
            self.scanThread.start()

        self.scanThread.paused.clear()
        self.updateCancelled.clear()

        if self.autoUpdate:
            self.updateTimer.Start(self.autoUpdate)


    def stopUpdater(self):
        """ Terminate the display updating threads and timers.
        """
        self.updateTimer.Stop()
        self.updateCancelled.set()

        if self.scanThreadRunning():
            self.scanThread.stop.set()


    def pauseUpdater(self):
        """ Temporarily pause the display updating. Resume it with
            `startUpdater()`.
        """
        self.updateTimer.Stop()
        if self.scanThreadRunning():
            self.scanThread.paused.set()


    def scanThreadRunning(self) -> bool:
        """ Is the device scan thread running?
        """
        return self.scanThread and self.scanThread.is_alive()


    def startThreads(self,
                     what: str,
                     devlist: list[tuple[Recorder, Callable, tuple, dict]],
                     timeout: float = 5.0,
                     dialog: bool = True,
                     ignore: Optional[type] = None) -> tuple[list, list, list]:
        """ Run commands on multiple devices, each in its own thread.

            :param what: Description of the command being run. For display
                purposes.
            :param devlist: A list of tuples containing the device, the
                function to execute, a tuple of positional arguments for
                the function, and a dictionary of keyword arguments.
            :param timeout: How long to wait for all threads to complete.
            :param dialog: If `True`, show a modal error dialog if
                any devices failed.
            :param ignore: A class of exception to exclude from the list of
                failures.
            :return: Three lists: successful executions, failures, and
                ones that failed to complete before the timeout.
        """
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        self.enableButtons(False)

        successes = []
        failures = []
        timeouts = []

        try:
            self.updateTimer.Stop()
            threads = []
            for dev, cmd, args, kwargs in devlist:
                if 'callback' in kwargs and kwargs['callback'] is None:
                    kwargs.pop('callback', None)
                else:
                    kwargs.setdefault('callback', self.isDead)
                threads.append(DeviceCommandThread(dev, cmd, *args, **kwargs))

            if timeout:
                deadline = time() + timeout
                while any(t.is_alive() for t in threads):
                    if time() > deadline:
                        break
                    if self.isDead():
                        break
                    sleep(0.05)

            names = []

            for t in threads:
                if t.failed.is_set():
                    if ignore and isinstance(t.failure, ignore):
                        continue
                    logger.error(f'{t.command.__name__} failed on {t.device}: {t.failure!r}')
                    failures.append(t)
                    names.append(f"{t.device.productName} SN:{t.device.serial} (error)")
                elif t.is_alive():
                    logger.error(f'{t.command.__name__} did not complete on {t.device} within {timeout} seconds')
                    timeouts.append(t)
                    names.append(f"{t.device.productName} SN:{t.device.serial} (timed out)")
                else:
                    successes.append(t)

            if dialog and (failures or (timeouts and timeout)) and not self.isDead():
                if names:
                    names = '\u2022 ' + ('\n\u2022 '.join(sorted(names)))
                    msg = (f"Could not {what} on all devices\n\n"
                           "The action was unsuccessful on these recorders:\n\n"
                           f"{names}")

                    wx.MessageBox(msg, "Device Error", parent=self,
                                  style=wx.OK | wx.ICON_ERROR)

        finally:
            if not self.isDead():
                self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
                self.enableButtons(True)

                if self.autoUpdate:
                    self.updateTimer.Start(self.autoUpdate)

        return successes, failures, timeouts


    def getChecked(self) -> List[Recorder]:
        """ Get the devices for all checked, enabled list items.
        """
        return [rec for rec in list(self.checkedRecorders)
                if self.list.GetItem(self.indicesByRecorder[rec]).IsEnabled()]


    def startRecording(self, *devices):
        """ Start one or more devices recording (assuming they can record).
        """
        # TODO: Better identification of valid devices (correct status, etc.)
        recorders = [(dev, dev.command.startRecording, (), {})
                     for dev in devices if dev.command.canRecord]

        # TODO: Handle errors better
        self.startThreads('start recording', recorders)


    def startStreaming(self, *devices):
        """ Start one or more devices streaming (assuming they can stream).
        """
        def _startStreaming(dev, path, **kwargs):
            dev.command.saveStream(path)
            dev.command.startRecording(**kwargs)

        path = os.path.abspath(self.savePathField.GetValue())
        if not os.path.isdir(path):
            wx.MessageBox(f'Invalid output path\n\nThe directory "{path}"\n'
                          'does not exist.', style=wx.ICON_ERROR)
            return

        # TODO: Better identification of valid devices (correct status, etc.)
        streamers = [(dev, _startStreaming, (dev, path), {})
                     for dev in devices if dev.command.canStream]

        # TODO: Handle errors better
        self.startThreads('start streaming', streamers)


    def clearRecorderCache(self):
        """ Clear cached recorder information and remove remote recorders
            from the caches.
        """
        try:
            self.pauseUpdater()
            if self.scanThreadRunning():
                self.scanThread.clearCache()
            with _module_busy:
                self.recorders = [dev for dev in self.recorders
                                  if not isinstance(dev._command, MQTTCommandInterface)]
                self.recordersByIndex.clear()
                self.indicesByRecorder.clear()
                self.recorderStatus.clear()
                self.recorderTimeouts.clear()
                # RECORDERS.clear()
        finally:
            self.startUpdater()


    def selectBroker(self):
        """ Open the broker selection dialog. The selected `MQTTConnector`
            is communicated back via an `EVT_BROKER_SELECTED` event.
        """
        self.connectFailTimer.Stop()
        self.disconnectTimer.Stop()
        self.setBrokerMessage('')

        try:
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROWWAIT))
            self.pauseUpdater()
            with BrokerDialog(self) as dlg:
                dlg.ShowModal()
        finally:
            self.startUpdater()
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    def getDefaultBroker(self):
        """ Start a `BrokerConnectThread` to find the default broker. The
            `MQTTConnector` is communicated back via an `EVT_BROKER_SELECTED`
            event.
        """
        _thread = BrokerConnectThread(self, self, self.defaultBroker)


    def setBrokerMessage(self, message: str, error=False):
        """ Set the broker status message text.

            :param message: Message text.
            :param error: If `True`, use the error font color and show
                message with a warning icon.
        """
        if error:
            color = self.textColorError
            message = f'⚠ {message}'
        else:
            color = self.textColorNormal

        self.brokerMessageText.SetForegroundColour(color)
        self.brokerMessageText.SetLabel(message)


    def setBroker(self,
                  connector: Optional[MQTTConnector],
                  info: Dict[str, Any] = None):
        """ Set the broker to use.

            :param connector: A `MQTTConnector` connected to a broker.
            :param info: A copy of the data returned by `findBrokers()` or
                `getBroker()`
        """
        try:
            logger.debug(f'selected broker: {connector}')
            self.pauseUpdater()
            self.updatingDisplay.set()

            if self.connector:
                self.connector.connectCallback = None
                self.connector.disconnectCallback = None
                self.connector.updateCallback = None
                self.connector.disconnect()

            if connector:
                self.brokerNameField.SetValue(connector.name)
                connector.updateCallback = self.onMqttUpdate

                tt = ''
                if info is not None:
                    tt = "{name}.{serviceType}\nIP {host[0]}, port {port}".format(**info)
                self.brokerNameField.SetToolTip(tt)
            else:
                self.brokerNameField.SetValue('')
                self.brokerNameField.SetToolTip('')

            self.connector = connector
            self.brokerInfo = info
            self.clearRecorderCache()
            self.recorders = [dev for dev in self.recorders
                              if not isinstance(dev._command, MQTTCommandInterface)]

        finally:
            self.updatingDisplay.clear()
            self.startUpdater()

        wx.CallAfter(self.populateList)


    # =======================================================================
    # Callbacks (not wxPython events)
    # =======================================================================

    def isDead(self) -> bool:
        """ Callback function that indicates the dialog is still working.
            Primarily for use as a callback in threads sending commands
            to devices.
        """
        # TODO: This may need more work
        return (not self.updateTimer.IsRunning()
                and not self.scanThreadRunning())


    def onMqttUpdate(self, data, connector: Optional[MQTTConnector] = None):
        """ Callback function executed when the `MQTTConnector` receives
            a state update from the Device Manager.
        """
        logger.debug(f'onMqttUpdate({data!r}, {connector!r})')
        if self.scanThreadRunning() and connector == self.connector:
            self.scanThread.onUpdate(data)


    # =======================================================================
    # wxPython Event handling
    # =======================================================================

    def _updateTimeouts(self):
        now = time()
        for dev in self.scanThread.getDevices():
            self.recorderTimeouts[dev] = (
                now + self.MQTT_TIMEOUT if isinstance(dev._command, MQTTCommandInterface)
                else now + self.SERIAL_TIMEOUT
            )
            wx.Yield()
        self.recorderTimeouts = {k: v for k, v in self.recorderTimeouts.items() if now < v}


    def OnUpdateTimerTick(self, _evt: Optional[wx.TimerEvent] = None):
        """ Handle the device-scanning timer ticking.

            todo: move most of the work where lags occur into `DeviceScanThread.scan()`?
        """
        # A lag in this method longer than the update interval can result in
        # this getting called multiple times. Don't block, just bail.
        if self.updatingDisplay.is_set():
            logger.debug('Bailing from DeviceDialog.OnUpdateTimerTick - updatingDisplay is set')
            return

        try:
            # logger.debug('>>> entering updateTimer tick handler')
            now = time()
            self.updatingDisplay.set()

            drivesChanged = deviceChanged(recordersOnly=False)
            # logger.debug(f'=== 0: in updateTimer tick handler after {time() - now:.4f} seconds (post deviceChanged)')

            # wx.Yield()

            self._updateTimeouts()
            # logger.debug(f'=== 1: in updateTimer tick handler after {time() - now:.4f} seconds (post scanThread.getDevices)')

            # wx.Yield()

            new = list(self.recorderTimeouts)
            foundChanged = set(new) != set(self.recorders)
            self.recorders = new
            # logger.debug(f'=== 2: in updateTimer tick handler after {time() - now:.4f} seconds (post timeout filter)')

            newStatus = self.scanThread.getDeviceStatuses()
            statusChanged = newStatus != self.recorderStatus or now - self.lastUpdate > 10
            self.recorderStatus = newStatus
            # logger.debug(f'=== 3: in updateTimer tick handler after {time() - now:.4f} seconds (post getDeviceStatus)')

            if foundChanged:
                # Repopulate list
                logger.debug(f'scan {self.updateCount}: (re-)building list')
                self.populateList()

            elif drivesChanged or statusChanged:
                # update list
                logger.debug(f'scan {self.updateCount}: updating list')
                self.lastUpdate = now
                self.updateList(skip=False)

            if self.updateCount == 0:
                # First update; resize to fit list contents
                logger.debug('first update, fitting list to width')
                # noinspection PyUnresolvedReferences
                self.SetSize((self.listWidth + (self.GetDialogBorder() * 4), -1))
        finally:
            self.updatingDisplay.clear()

        self.updateCount += 1
        # logger.debug(f'<<< exiting updateTimer tick handler after {time() - now:.4f} seconds')


    def OnColClick(self, evt):
        # Required by ColumnSorterMixin
        evt.Skip()


    def OnItemSelected(self, evt):
        """ Handle list item (row) selection.
        """
        logger.debug('OnItemSelected')
        self.selected = self.list.GetItemData(evt.Index)
        if self.listMsgs[self.selected] is not None:
            self.infoText.SetLabel(self.listMsgs[self.selected])

        if self.selected not in self.recordersByIndex:
            logger.error(f'Could not get selected recorder with index {self.selected}!')
            self.okButton.Enable(False)
            evt.Skip()
            return

        recorder = self.recordersByIndex[self.selected]
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
        """ Hande list item (row) double-click.
        """
        if (self.allowDoubleClick and self.list.GetSelectedItemCount() > 0
                and self.okButton.IsEnabled()):
            # Close the dialog
            self.EndModal(wx.ID_OK)

        evt.Skip()


    def OnListMouseMotion(self, evt):
        """ Handle mouse movement, updating the tool tips, etc.
            This determines the list item under the mouse and shows the
            appropriate tool tip, if any
        """
        if not self.recordersByIndex or not self.tooltipFrame or self.menuOpen.is_set():
            evt.Skip()
            return

        self.tooltipFrame.timer.Stop()
        self.tooltipFrame.Hide()

        index, _ = self.list.HitTest(evt.GetPosition())
        if index != wx.NOT_FOUND:
            item = self.list.GetItemData(index)

            # Everything here on is part of ULC tooltip workaround.
            self.tooltipFrame.device = self.recordersByIndex[index]
            self.tooltipFrame.setText(self.listToolTips[item])
            self.lastToolTipItem = index
            if not self.tooltipFrame.IsShown():
                self.tooltipFrame.timer.StartOnce(self.tooltipFrame.TOOLTIP_TIME)

        evt.Skip()


    def OnListRightClick(self, evt):
        if not self.recordersByIndex or not self.tooltipFrame:
            evt.Skip()
            return

        index, _ = self.list.HitTest(evt.GetPosition())
        if index != wx.NOT_FOUND:
            try:
                self.pauseUpdater()
                self.updatingDisplay.set()
                self.menuOpen.set()

                self.tooltipFrame.timer.Stop()
                self.tooltipFrame.Hide()

                try:
                    device = self.recordersByIndex[index]
                except IndexError:
                    logger.error(f'OnListRightClick: No Recorder at index {index}, '
                                 f'list coordinates {evt.GetPosition()}!')
                    return

                menu = ListContextMenu(self, device, self.list, index)
                self.PopupMenu(menu)
                menu.Destroy()

            finally:
                self.menuOpen.clear()
                self.updatingDisplay.clear()
                self.startUpdater()

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
            if self.remote:
                checked = self.remoteCheck.GetValue()
                self.showBrokerSelection(checked)

            wx.CallAfter(self.OnUpdateTimerTick)
            self.startUpdater()

        else:
            if self.connector:
                self.connector.updateCallback = None
                self.connector.connectCallback = None
                self.connector.disconnectCallback = None
                # if self.ownConnector:
                #     self.connector.disconnect()
            self.stopUpdater()
            if self.tooltipFrame:
                self.tooltipFrame.timer.Stop()
                self.tooltipFrame.Hide()

        evt.Skip()
        

    def OnSetClocks(self, _evt=None):
        """ Set all clocks. Used as an event handler.
        """
        devices = [(rec, rec.setTime, (), {'callback': None})
                   for rec in self.recordersByIndex.values()]
        self.startThreads('set the clock', devices)


    def OnStartRecording(self, evt):
        """ Initiate a recording.

            :param evt: The event generated by a dialog 'Record' button, or
                an `EVT_RECORD_BUTTON` event from a row in the list.
        """
        # XXX: CLEAN THIS UP, USE startRecording()
        logger.debug('starting recording...')

        self.updateTimer.Stop()
        # TODO: Make sure updating threads all stopped?

        try:
            # If EVT_RECORD_BUTTON, get device from event, otherwise use selected
            recorder = getattr(evt, 'device', None)
            stop = getattr(evt, 'stop', False)
            if not recorder:
                recorder = self.recordersByIndex.get(self.selected, None)
            if recorder and recorder.canRecord:
                if stop:
                    DeviceCommandThread(recorder,
                                        recorder.command.stopRecording,
                                        callback=self.isDead)
                else:
                    DeviceCommandThread(recorder,
                                        recorder.command.startRecording,
                                        callback=self.isDead)
                self.updateRow(recorder, enabled=False)
        finally:
            # self.updateList()
            if self.autoUpdate:
                self.updateTimer.Start(self.autoUpdate)


    def OnStartStreaming(self, evt):
        """ Handle a device list 'stream' button or menu item selection.
        """
        logger.debug('starting stream...')
        self.updateTimer.Stop()
        # TODO: Make sure updating threads all stopped?

        try:
            # If EVT_STREAM, get device from event, otherwise use selected
            dev = getattr(evt, 'device', None)
            if not dev:
                dev = self.recordersByIndex.get(self.selected, None)
            if dev and dev.command.canStream:
                self.startStreaming(dev)
                self.updateRow(dev, enabled=False)
        finally:
            # self.updateList()
            if self.autoUpdate:
                self.updateTimer.Start(self.autoUpdate)


    def OnLockDevice(self, evt):
        """ Handle a device list 'lock' button or menu item selection.
        """
        device = evt.device
        clear = getattr(evt, 'clear', False)
        force = getattr(evt, 'force', False)

        # TODO: this whole thing might need to go into a thread, as
        #  `isLocked()` could potentially take time to execute.
        locked, mine = device.command.isLocked()
        current = device.command.getLockID() if force else None

        if locked and not mine and not force:
            logger.debug(f'Tried to unlock {device.serial}, claimed by another')
            return
        elif clear:
            logger.debug(f'Clearing lock on device {device.serial}')
            DeviceCommandThread(device, device.command.clearLockID, current=current)
        else:
            logger.debug(f'Setting lock on device {device.serial}')
            DeviceCommandThread(device, device.command.setLockID, current=current)

        wx.CallAfter(self.updateList)


    def OnBlink(self, evt):
        """ Handle a device list 'blink LEDs' button or menu item selection.
        """
        logger.debug(f'Sending Blink to {evt.device}')
        DeviceCommandThread(evt.device, evt.device.command.blink)


    def OnConfigButton(self, evt):
        """ Handle a device list 'configure' button or menu item selection.
        """
        logger.debug(f'Handling config event for {evt.device}')
        if self.okButton.IsEnabled():
            self.EndModal(wx.ID_OK)


    def OnRebootDevice(self, evt):
        """ Handle the 'reboot' button or menu item selection.
        """
        promptDeviceReboot(evt.device, self)


    def OnShutdownDevice(self, evt):
        """ Handle the 'shutdown' button or menu item selection.
        """
        promptDeviceShutdown(evt.device, self)


    def OnStartAllRecorders(self, evt):
        """ Send the 'start recording' command to all devices.

            This is placeholder for future functionality. It may or may not
            ever be implemented.
        """
        # If/when this is implemented, it will be like `OnSetClocks()`
        logger.warning("OnStartAllRecorders() is not implemented (yet)!")
        evt.Skip()


    def OnStartSelected(self, _evt):
        """ Handle the 'Start Checked' button press event.
        """
        devices = [(rec, rec.command.startRecording, (), {})
                   for rec in self.getChecked()
                   if rec.command.canRecord]

        # TODO: Handle errors better
        self.startThreads('start recording', devices)


    def OnStreamSelected(self, _evt):
        """ Handle the 'Stream from Checked' button press event.
        """
        devs = [dev for dev in self.getChecked() if dev.command.canStream]
        self.startStreaming(*devs)


    def OnStopSelected(self, _evt):
        """ Stop all checked devices.
        """
        def _stopRecording(dev, **kwargs):
            dev.command.stopRecording(**kwargs)
            dev.command.closeStream()

        # TODO: Better identification of valid devices (correct status, etc.)
        devices = [(rec, _stopRecording, (rec,), {})
                   for rec in self.getChecked()
                   if rec.command.canRecord]

        # TODO: Handle errors better
        self.startThreads('stop recording/streaming', devices, ignore=CommandError)


    def OnItemChecked(self, evt):
        """ Handle an item check.
        """
        item = evt.GetItem()
        idx = evt.GetIndex()
        if idx < 0:
            logger.debug(f'{idx=} (bad)')
            evt.Skip()
            return
        dev = self.recordersByIndex[idx]
        if item.IsChecked():
            self.checkedRecorders.add(dev)
        else:
            try:
                self.checkedRecorders.remove(dev)
            except KeyError:
                pass
        self.updateList()
        evt.Skip()


    def OnSavePathPicked(self, _evt):
        """ Handle an output directory being chosen.
            Note: called with every keystroke in the `DirBrowseButton`
        """
        pass
        # self.saveCheck.SetValue(True)


    def OnSelectAllButton(self, _evt):
        logger.debug('Check all')
        self.checkedRecorders.clear()
        for idx, dev in self.recordersByIndex.items():
            if self.list.IsItemEnabled(idx):
                self.checkedRecorders.add(dev)
        self.updateList()


    def OnSelectNoneButton(self, _evt):
        logger.debug('Check none')
        self.checkedRecorders.clear()
        self.updateList()


    # =======================================================================
    # MQTT-related events
    # =======================================================================

    def OnRemoteCheckChanged(self, _evt):
        """ Handle the 'remote' checkbox changing. Also used to update
            things on startup.
        """
        self.connectFailTimer.Stop()
        self.disconnectTimer.Stop()
        self.setBrokerMessage('')

        checked = self.remoteCheck.GetValue()
        self.showBrokerSelection(checked)
        if checked:
            self.selectBroker()
        else:
            self.setBroker(None)


    def OnBrokerSelect(self, _evt):
        """ Handle the broker 'Select...' button press.
        """
        self.selectBroker()


    def OnBrokerSelected(self, evt):
        """ Handle an MQTT broker selection.
        """
        # self.brokerPane.Enable()
        self.showBrokerSelection()
        connector = getattr(evt, 'connector', None)
        info = getattr(evt, 'info', None)

        logger.debug(f'OnSetBrokerSelected() -> {info}')
        self.setBroker(connector, info)


    def OnMQTTConnecting(self, _evt):
        """ Handle the `BrokerConnectThread` starting.
        """
        # self.brokerPane.Disable()
        self.showBrokerSelection(False)
        self.disconnectTimer.Stop()
        self.setBrokerMessage('Connecting...')
        self.connectFailTimer.StartOnce(CONNECT_FAIL_TIMEOUT)


    def OnMQTTConnected(self, _evt):
        """ Handle a MQTT client connection event, posted by
            `MQTTConnector.connectCallback`.
        """
        self.connectFailTimer.Stop()
        self.disconnectTimer.Stop()
        # self.brokerPane.Enable()
        self.showBrokerSelection()
        self.setBrokerMessage('Connected')


    def OnMQTTDisconnected(self, _evt):
        """ Handle a MQTT client disconnection event, posted by
            `MQTTConnector.disconnectCallback`.
        """
        self.connectFailTimer.Stop()
        # self.brokerPane.Enable()
        self.showBrokerSelection()
        self.setBrokerMessage('Disconnected')
        self.disconnectTimer.StartOnce(DISCONNECT_TIMEOUT)


    def OnMQTTError(self, evt):
        """ Handle a MQTT error event.
        """
        self.connectFailTimer.Stop()
        self.disconnectTimer.Stop()
        # self.brokerPane.Enable()
        self.showBrokerSelection()
        self.setBrokerMessage(evt.message, error=True)


    def OnDisconnectTimer(self, _evt):
        try:
            logger.debug(f'Broker disconnected too long, removing MQTT devices')
            self.pauseUpdater()
            self.updatingDisplay.set()
            self.clearRecorderCache()
            self.recorders = [dev for dev in self.recorders
                              if not isinstance(dev._command, MQTTCommandInterface)]
        finally:
            self.updatingDisplay.clear()
            self.startUpdater()

        wx.CallAfter(self.populateList)


    def OnConnectFailTimer(self, _evt):
        """ Handle a contingency timeout event (i.e., the `BrokerConnectThread`
            failed in some unexpected way).
        """
        evt = EvtMQTTError("Timed out starting broker connection")
        wx.PostEvent(self, evt)


# ===========================================================================
#
# ===========================================================================

def selectDevice(title: str = "Select Recorder",
                 parent: Optional[wx.Window] = None,
                 **kwargs):
    """ Display a device-selection dialog and return the path to a recorder.
        The dialog will (optionally) update automatically when devices are
        added or removed.

        :keyword filter: An optional function to exclude devices from the
            list. It should take a `Recorder` as an argument, and return a
            boolean.
        :keyword autoUpdate: A number of milliseconds to delay between
            checks for changes to attached recorders. 0 will never
            automatically refresh. Default is 500 ms.
        :keyword scanInterval: The number of milliseconds between
            scans for new devices. Default is 4000 ms.
        :keyword showWarnings: If `False`, battery age and calibration
            expiration warnings will not be shown for selected devices.
            Default is `True`.
        :keyword showConnection: If `True`, the connection type icon
            (USB, Wi-Fi, Bluetooth) will be shown on the left side of
            each devices' row.
        :keyword showAdvanced: If `True`, show additional columns of
            information (hardware/firmware version, etc.). Default is
            `False`.
        :keyword hideClock: If `True`, the "Set all clocks" button will be
            hidden. Default is `False`.
        :keyword hideRecord: If `True`, the "Start Recording" button will be
            hidden. Default is `False`.
        :keyword okText: Alternate text to display on the OK/Configure
            button. Defaults to `"Configure"`.
        :keyword okHelp: Alternate tooltip for the OK/Configure button.
            Defaults to `"Configure the selected device"`.
        :keyword cancelText: Alternate text to display on the Cancel/Close
            button. Defaults to `"Close"`
        :keyword icon: A `wx.Icon` for the dialog (for platforms that support
            title bar icons). `None` (default) will use the package default.
            `False` will show no icon.
        :keyword tooltips: If `True` (default), show list tooltips containing
            all important device infomation.
        :keyword checks: If `True`, show checkboxes for each device.
        :keyword allowDoubleClick: If `True`, double-clicking a list item
            will be the same as selecting it and clicking OK. Defaults to
            `False` if `checks` is `True`.
        :keyword mustConfig: If `True`, the 'OK' button will only become
            enabled if the device can be configured.
        :keyword remote: If `True`, show the MQTT broker selection field.
        :keyword remoteChecked: The initial state of the 'use remote'
            checkbox, if `remote` is `True`. `True` by default.
        :keyword broker: The name of the default, initially selected broker.
            `None` will select the first found.
        :keyword connector: An existing `endaq.device.mqtt.MQTTConnector`
            instance, if one was already created.
        :keyword showSave: If `True`, show the save path selector.
        :keyword savePath: The default save path for streams.
        :return: The path of the selected device.
    """
    result = None

    with DeviceSelectionDialog(parent, -1, title, **kwargs) as dlg:
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.getSelected()

        # Disconnect from broker if no device selected and broker connection
        # wasn't pre-existing (i.e., the same as the one provided as
        # `connector` kwarg)
        if (result is None and dlg.connector is not None
                and kwargs.get('connector') != dlg.connector):
            dlg.connector.disconnect()

    return result
