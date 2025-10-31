"""
Dialog for selecting and/or controlling recording devices.

"""

from collections import namedtuple
import datetime
from functools import partial
import logging
import os.path
import threading
from time import sleep, time
from typing import Callable, Dict, List, Optional, Tuple, Union

import wx
import wx.lib.sized_controls as sc
import wx.lib.mixins.listctrl as listmix
from wx.lib.agw import ultimatelistctrl as ULC
import wx.lib.filebrowsebutton as FBB

from endaq.device import (Recorder, RECORDERS, UnsupportedFeature,
                          DeviceError, deviceChanged)
from endaq.device.base import os_specific
# from endaq.device.response_codes import DeviceStatusCode
from endaq.device.mqtt.mqtt_interface import MQTTCommandInterface, MQTTConnector

from . import battery_icons
from . import icons
from .controls import (_attribFormatter, populateStatusColumn,
                       populateButtonColumn, populateBatteryColumn, NewControlButtons)
from .events import EvtRecordButton, EVT_RECORD_BUTTON, EVT_BROKER_UPDATE
from .threads import DeviceScanThread, DeviceCommandThread, getDeviceStatus
from .shared import DeviceToolTip, BrokerField

logger = logging.getLogger(__name__)

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
            :keyword showSave: If `True`, show the save path selector.
            :keyword savePath: The default save path for streams.
        """
        # Clear cached devices
        RECORDERS.clear()

        self.autoUpdate: Union[int, bool] = kwargs.pop('autoUpdate', 500)
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

        defaultBroker: Optional[str] = kwargs.pop('broker', None)
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

        if icon or icon is None:
            icon = icon or icons.icon.GetIcon()
            self.SetIcon(icon)

        self.updateTimer = wx.Timer(self)
        self.updateCount = 0
        self.updateCancelled = threading.Event()  # Use as callback for getBatteryStatus/ping commands
        self.scanThread: DeviceScanThread = None

        self.updatingDisplay = threading.Event()  # Set while updating, so other calls skip.

        self.recorders: List[Recorder] = []  # The currently-displayed recorders.
        self.recorderStatus: Dict[Recorder, Tuple] = {}  # Recorder status, battery state, and path, keyed by `Recorder`
        self.recorderTimeouts: Dict[Recorder, float] = {}  # Time to remove a recorder from `recorderStatus` if not in `getDevices()`
        self.recordersByIndex: Dict[int, Recorder] = {}  # `Recorder` instances keyed by list index.
        self.indicesByRecorder: Dict[Recorder, int] = {}  # List index keyed by `Recorder`
        self.updatingRecorders = threading.RLock()  # To avoid simultaneous dict changes

        self.checkedRecorders: set[Recorder] = set()  # Checked items/recorders (to keep checks after list updates)

        self.brokerInfo = None  # Selected MQTT broker's mDNS info
        self.connector: MQTTConnector = None

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

        if self.remote is not None:
            self._addBrokerSelect(pane, default=defaultBroker)

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
        self.Bind(EVT_RECORD_BUTTON, self.OnStartRecording)
        self.Bind(wx.EVT_TIMER, self.OnUpdateTimerTick, id=self.updateTimer.GetId())


    # TODO: REMOVE NEXT COMMENT LATER (linter doesn't like monkeypatched sizer methods, clutters everything up)
    # noinspection PyUnresolvedReferences
    def _addBrokerSelect(self, pane, default=None):
        """ Add MQTT Broker selection widgets.
        """
        selpane = sc.SizedPanel(pane, -1)
        selpane.SetSizerType("horizontal")
        selpane.SetSizerProps(expand=True)
        self.remoteCheck = wx.CheckBox(selpane, -1, "Show Remote Devices")
        self.remoteCheck.SetSizerProps(valign='centre')

        self.brokerList = BrokerField(selpane, default=default)
        self.brokerList.SetSizerProps(valign='center', expand=True)

        self.remoteCheck.SetValue(self.remote)
        self.brokerList.Show(self.remote)

        self.remoteCheck.Bind(wx.EVT_CHECKBOX, self.OnRemoteCheckChanged)
        self.Bind(EVT_BROKER_UPDATE, self.OnBrokerSelected)


    # TODO: REMOVE NEXT COMMENT LATER (linter doesn't like monkeypatched sizer methods, clutters everything up)
    # noinspection PyUnresolvedReferences
    def _addStreamTo(self, pane, default=''):
        """ Add stream save directory selection selection widgets.
        """
        selpane = sc.SizedPanel(pane, -1)
        selpane.SetSizerType("horizontal")
        selpane.SetSizerProps(expand=True)
        self.saveCheck = wx.CheckBox(selpane, -1, "")
        self.saveCheck.SetSizerProps(valign='centre')

        self.savePathField = FBB.DirBrowseButton(selpane,
                                                 labelText="Save streams to:",
                                                 initialValue=default,
                                                 changeCallback=self.OnSavePathPicked)
        self.savePathField.SetSizerProps(valign='center', expand=True, proportion=1)

        # self.saveCheck.SetValue(self.remote)
        # self.savePathField.Show(self.remote)

        # self.saveCheck.Bind(wx.EVT_CHECKBOX, self.OnSaveCheckChanged)


    # TODO: REMOVE NEXT LINE LATER (linter doesn't like monkeypatched sizer methods, clutters everything up)
    # noinspection PyUnresolvedReferences
    def _addSelectButtons(self, pane, defaultPath=''):
        """ Add buttons for selecting and controlling selected items.
        """
        NewControlButtons._loadImages()
        startIcons = NewControlButtons.ICONS[1]
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
        self.Bind(wx.EVT_BUTTON, self.OnStartSelected, self.multiStartBtn)
        self.Bind(wx.EVT_BUTTON, self.OnStreamSelected, self.multiStreamBtn)


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

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self.list)
        self.list.Bind(wx.EVT_LEFT_DCLICK, self.OnItemDoubleClick)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self.list)

        if self.checks:
            self.Bind(ULC.EVT_LIST_ITEM_CHECKED, self.OnItemChecked, self.list)

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
        if self.updatingDisplay.is_set():
            # Prevent simultaneous updates by just bailing if one's already going
            return

        try:
            logger.debug('populating list')
            self.updatingDisplay.set()
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
            self.updatingDisplay.clear()
            logger.debug('populating list complete')


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

        # status = self.recorderStatus.get(dev, (None, (DeviceStatusCode.IDLE, '')))[1][0]
        enabled = enabled and self.recorderStatus[dev][-2]  # dev.command.available

        # enable or disable the row
        # excludes button panel - do that explicitly
        item = self.list.GetItem(index)
        item.Enable(enabled)
        item.Check(dev in self.checkedRecorders)
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

        checked = self.list.GetCheckedItemCount()
        self.multiStreamBtn.Enable(checked > 0)
        self.multiStartBtn.Enable(checked > 0)


    def updateList(self):
        """ Update the statuses in the displayed list of devices. Called in
            response to a message from the device scanning thread if no
            devices have been added or removed.

            :see: OnDeviceListUpdate()
        """
        # Bail if an update is already being handled
        # (e.g., called from a different thread)
        if self.updatingDisplay.is_set():
            return

        try:
            self.updatingDisplay.set()
            # logger.debug('Updating display')
            for dev in self.recorders:
                self.updateRow(dev)

        finally:
            self.updatingDisplay.clear()


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
        """ Start the disply updating threads and timers.
        """
        if not self.scanThread or not self.scanThread.is_alive():
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
        self.updatingDisplay.set()

        if self.scanThread and self.scanThread.is_alive():
            self.scanThread.stop.set()


    def pauseUpdater(self):
        """ Temporarily pause the display updating. Resume it with
            `startUpdater()`.
        """
        self.updateTimer.Stop()
        if self.scanThread and self.scanThread.is_alive():
            self.scanThread.paused.set()


    def startThreads(self,
                     devlist: list[tuple[Recorder, Callable, tuple, dict]],
                     timeout: float = 5.0,
                     dialog: bool = True) -> tuple[list, list, list]:
        """ Run commands on multiple devices, each in its own thread.

            :param devlist: A list of tuples containing the device, the
                function to execute, a tuple of positional arguments for
                the function, and a dictionary of keyword arguments.
            :param timeout: How long to wait for all threads to complete.
            :param dialog: If `True`, show a modal error dialog if
                any devices failed.
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
            threads = [DeviceCommandThread(dev, cmd, *args, **kwargs)
                       for dev, cmd, args, kwargs in devlist]

            if timeout:
                deadline = time() + timeout
                while any(t.is_alive() for t in threads):
                    if time() > deadline:
                        break
                    sleep(0.05)

            for t in threads:
                if t.failed.is_set():
                    logger.error(f'{t.command.__name__} failed on {t.device}: {t.failure!r}')
                    failures.append(t)
                elif t.is_alive():
                    logger.error(f'{t.command.__name__} did not complete on {t.device} within {timeout} seconds')
                    timeouts.append(t)
                else:
                    successes.append(t)

            if dialog and failures or (timeouts and timeout):
                if failures:
                    if len(failures) > 1:
                        names = "\u2022 " + ('\n\u2022 '.join(failures))
                        # XXX: Chnange dialog contents
                        msg = ("Could not set recorder clocks.\n\n"
                               "Errors prevented the clocks being set on these recorders:\n\n"
                               f"{names}")
                    else:
                        msg = ("Could not set recorder clock.\n\n"
                               "An error prevented the clock from being set on "
                               f"recorder {failures[0]}.")

                    wx.MessageBox(msg, "Device Error", parent=self,
                                  style=wx.OK | wx.ICON_ERROR)

        finally:
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            self.enableButtons(True)

            if self.autoUpdate:
                self.updateTimer.Start(self.autoUpdate)

        return successes, failures, timeouts


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
                and not (self.scanThread and self.scanThread.is_alive()))


    def onMqttUpdate(self, data):
        """ Callback function executed when the `MQTTConnector` receives
            a state update from the Device Manager.
        """
        if self.scanThread and self.scanThread.is_alive():
            self.scanThread.onUpdate(data)


    # =======================================================================
    # wxPython Event handling
    # =======================================================================

    def OnUpdateTimerTick(self, _evt: Optional[wx.TimerEvent] = None):
        """ Handle the device-scanning timer ticking.
        """
        now = time()

        drivesChanged = deviceChanged(recordersOnly=False)  # XXX: remove this?
        foundChanged = False
        statusChanged = False

        with self.updatingRecorders:
            for dev in self.scanThread.getDevices():
                self.recorderTimeouts[dev] = (
                    now + self.MQTT_TIMEOUT if isinstance(dev.command, MQTTCommandInterface)
                    else now + self.SERIAL_TIMEOUT
                )

            self.recorderTimeouts = {k: v for k, v in self.recorderTimeouts.items() if now < v}
            new = list(self.recorderTimeouts)
            foundChanged = set(new) != set(self.recorders)
            self.recorders = new

        with self.updatingRecorders:
            newStatus = {dev: getDeviceStatus(dev) for dev in self.recorders}
            statusChanged = newStatus != self.recorderStatus or now - self.lastUpdate > 10
            self.recorderStatus = newStatus

        if foundChanged:
            # Repopulate list
            logger.debug(f'scan {self.updateCount}: (re-)building list')
            self.populateList()

        elif drivesChanged or statusChanged:
            # update list
            # logger.debug(f'scan {self.updateCount}: updating list')
            self.lastUpdate = now
            self.updateList()

        if self.updateCount == 0:
            # First update; resize to fit list contents
            logger.debug('first update, fitting list to width')
            self.SetSize((self.listWidth + (self.GetDialogBorder() * 4), -1))

        self.updateCount += 1


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
            logger.error(f'Could not get selected recorder with index {self.selected}!')
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
        if not self.recordersByIndex or not self.tooltipFrame:
            evt.Skip()
            return

        # Part of workaround for broken ULC tooltips. It can probably be removed
        # if/when ULC tooltips get fixed.
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
            try:
                if self.remote:
                    if self.remoteCheck.IsChecked():
                        wx.CallAfter(self.brokerList.postSelectionEvent)
            except Exception as err:
                logger.error(f'Failed to post first broker selection event: {err!r}')

            wx.CallAfter(self.OnUpdateTimerTick)
            self.startUpdater()

        else:
            self.stopUpdater()
            if self.tooltipFrame:
                self.tooltipFrame.timer.Stop()
                self.tooltipFrame.Hide()
            if self.connector:
                self.connector.disconnect()

        evt.Skip()
        

    def OnSetClocks(self, _evt=None):
        """ Set all clocks. Used as an event handler.
        """
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        self.enableButtons(False)

        try:
            self.updateTimer.Stop()

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

            if self.autoUpdate:
                self.updateTimer.Start(self.autoUpdate)


    def OnStartRecording(self,
                         evt: Union[wx.CommandEvent, EvtRecordButton, None] = None):
        """ Initiate a recording.

            :param evt: The event generated by a dialog 'Record' button, or
                an `EVT_RECORD_BUTTON` event from a row in the list.
        """
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
                    # recorder.command.stopRecording()
                    DeviceCommandThread(recorder, recorder.command.stopRecording,
                                        callback=self.isDead)
                else:
                    # recorder.command.startRecording()
                    DeviceCommandThread(recorder, recorder.command.startRecording,
                                        callback=self.isDead)
                self.updateRow(recorder, enabled=False)
        finally:
            # self.updateList()
            if self.autoUpdate:
                self.updateTimer.Start(self.autoUpdate)


    def OnStartAllRecorders(self,
                            evt: Union[wx.CommandEvent, EvtRecordButton, None] = None):
        """ Send the 'start recording' command to all devices.

            This is placeholder for future functionality. It may or may not
            ever be implemented.
        """
        # If/when this is implemented, it will be like `OnSetClocks()`
        logger.warning("OnStartAllRecorders() is not implemented (yet)!")
        evt.Skip()


    def OnStartSelected(self, _evt):
        # TODO: XXX: IMPLEMENT
        devices = [dev for dev in list(self.checkedRecorders) if dev.command.canRecord]

        logger.debug('Start selected not implemented!')


    def OnStreamSelected(self, _evt):
        # TODO: XXX: IMPLEMENT
        devices = [dev for dev in list(self.checkedRecorders) if dev.command.canStream]
        logger.debug('Stream from selected not implemented!')


    def OnRemoteCheckChanged(self, _evt):
        """ Handle the 'remote' checkbox changing. Also used to update
            things on startup.
        """
        checked = self.remoteCheck.GetValue()
        self.brokerList.Show(checked)
        self.populateList()


    def OnBrokerSelected(self, evt):
        """ Handle an MQTT broker selection.
        """
        info = evt.broker
        if not info:
            logger.debug("No broker info in selection event, bad broker address?")
            return
        elif info == self.brokerInfo:
            logger.debug('same broker selected, ignoring')
            return

        oldConnector = self.connector
        if oldConnector:
            oldConnector.disconnect()

        try:
            newcon = MQTTConnector(info['host'], info['port'], name=info['name'],
                                   updateCallback=self.onMqttUpdate)
            newcon.connect()
            self.connector = newcon
            self.brokerInfo = info

            self.recorders = []
            self.recorderStatus.clear()
            self.recorderTimeouts.clear()
            self.recordersByIndex.clear()
            self.indicesByRecorder.clear()

        except Exception:
            if oldConnector:
                self.connector = oldConnector
                self.connector.connect()
            raise

        wx.CallAfter(self.OnUpdateTimerTick)


    def OnItemChecked(self, evt):
        """ Handle an item check.
        """
        item = evt.GetItem()
        idx = evt.GetIndex()
        if idx < 0:
            logger.debug(f'OnItemChecked: {idx=} (bad)')
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
