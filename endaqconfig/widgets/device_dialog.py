"""
Dialog for selecting and/or controlling recording devices.

"""

from collections import namedtuple
from datetime import datetime, timedelta
from functools import partial
import logging
import os.path
from typing import Optional

import wx
import wx.lib.sized_controls as sc
import wx.lib.mixins.listctrl as listmix
from wx.lib.agw import ultimatelistctrl as ULC

from endaq.device import Recorder, getDevices, getDeviceList, RECORDERS
from endaq.device import deviceChanged, CommandError, UnsupportedFeature
from endaq.device.base import os_specific

from .shared import DeviceToolTip
from . import icons
from . import battery_icons
from . import controls
from .events import EVT_CONFIG_BUTTON, EVT_RECORD_BUTTON

logger = logging.getLogger('endaqconfig')

# XXX: For testing, remove
from itertools import cycle
GUI_DEMO = not True

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
# Column 'formatters.' They actually add the column to the list and return
# the value for the list sorting.
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
    # XXX: For testing two (and a half) different button approaches
    pan = controls.ControlButtons(root, root.list, dev, index, column)
    # pan = controls.ControlImageButtons(root, root.list, dev, index, column, plates=True)

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

    try:
        # TODO: Don't call getBatteryState() here; call elsewhere and cache response
        batName, batDesc = battery_icons.batStat2name(dev.command.getBatteryStatus())
        batIcon = root.batteryIconIndices.get(batName, 0)
    except (CommandError, UnsupportedFeature):
        batIcon, batDesc = 0, ''

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

    status = ""
    code = 0

    try:
        # TODO: Use status in cached getBatteryState() response
        dev.command.ping()
        code, msg = dev.command.status
        if code is not None:
            status = str(code)
            if '.' in status:
                status = status.rpartition('.')[-1].title().replace('Err', 'Error')
            if msg:
                status = f"{status}: {msg}"
    except UnsupportedFeature:
        status = ""

    root.list.SetStringItem(index, column, status)

    # XXX: Test.
    #  TODO: Move to whatever updates the display.
    if code:
        # Find specific color, or round to lowest multiple of 10
        code = code if code in root.STATUS_COLORS else code // 10
        color = root.STATUS_COLORS.get(code, None)
        if not color and code < 0:
            color = root.STATUS_COLORS.get(-10)

        if color:
            font = root.list.GetFont()
            item = root.list.GetItem(index, column)
            item.SetMask(ULC.ULC_MASK_FONTCOLOUR|ULC.ULC_MASK_FONT)
            item.SetTextColour(wx.BLUE)
            item.SetFont(font)
            root.list.SetItem(item)

    return code


# ===========================================================================
#
# ===========================================================================

class DeviceSelectionDialog(sc.SizedDialog, listmix.ColumnSorterMixin):
    """ The dialog for selecting data to export.
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
        "Bat.": populateBatteryColumn,
        "Device Control": populateButtonColumn
    }

    ADVANCED_COLUMNS = {
        "Path": partial(_attribFormatter, "path", ""),
        "Name": partial(_attribFormatter, "name", ""),
        "Type": partial(_attribFormatter, "productName", ""),
        "Serial #": partial(_attribFormatter, "serial", ""),
        "Status": populateStatusColumn,
        # "HW Rev.": partial(_attribFormatter, "hardwareVersion", ''),
        # "FW Rev.": partial(_attribFormatter, "firmware", ''),
        "Bat.": populateBatteryColumn,
        "Device Control": populateButtonColumn,
        # "Configuration": populateConfigColumn,
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
        -10: wx.RED  # Error
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
        self.showAdvanced = kwargs.pop('showAdvanced', False) or True
        self.filter = kwargs.pop('filter', lambda x: True)
        self.checks = kwargs.pop('checks', False)
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

        # TODO: Better column collection (assemble piecemeal based on parameters)
        if self.showAdvanced:
            self.columns = [self.ColumnInfo(name, formatter)
                            for name, formatter in self.ADVANCED_COLUMNS.items()]
        else:
            self.columns = [self.ColumnInfo(name, formatter)
                            for name, formatter in self.COLUMNS.items()]

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

        self.recorders = {}
        self.recorderPaths = tuple(getDeviceList())
        self.selected = None
        self.selectedIdx = None
        self.firstDrawing = True
        self.listWidth = 0

        pane = self.GetContentsPane()
        pane.SetSizerProps(expand=True)

        self.itemDataMap = {}  # required by ColumnSorterMixin

        self.list = ULC.UltimateListCtrl(pane, -1,
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

        # Selected device info
        self.infoText = wx.StaticText(pane, -1, "")
        self.infoText.SetSizerProps(expand=True)

        buttonpane = sc.SizedPanel(pane, -1)
        buttonpane.SetSizerType("horizontal")
        buttonpane.SetSizerProps(expand=True)

        self.setClockButton = wx.Button(buttonpane, self.ID_SET_TIME,
                                        "Set All Clocks")
        self.setClockButton.SetSizerProps(halign="left")
        self.setClockButton.SetToolTip("Set the time of every attached "
                                       "recorder with a real-time clock")

        self.recordButton = wx.Button(buttonpane, self.ID_START_RECORDING,
                                      "Start Recording")
        self.recordButton.SetSizerProps(halign="left")
        self.recordButton.SetToolTip(self.RECORD_ENABLED)
        self.recordButton.Enable(False)

        sc.SizedPanel(buttonpane, -1).SetSizerProps(proportion=1)  # Spacer

        self.okButton = wx.Button(buttonpane, wx.ID_OK, okText)
        self.okButton.SetToolTip(okHelp)
        self.okButton.SetSizerProps(halign="right")
        self.okButton.Enable(False)
        self.cancelButton = wx.Button(buttonpane, wx.ID_CANCEL, cancelText)
        self.cancelButton.SetSizerProps(halign="right")

        # Call deviceChanged() to set the initial state. Result ignored.
        deviceChanged(recordersOnly=False, clear=True)
        self.populateList()
        self.list.Fit()

        listmix.ColumnSorterMixin.__init__(self, len(self.columns))

        self.Fit()
        self.SetSize((self.listWidth + (self.GetDialogBorder()*4), 300))
        self.SetMinSize((400, 300))
        self.SetMaxSize((1500, 600))

        self.Layout()
        self.Centre()

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self.list)
        self.list.Bind(wx.EVT_LEFT_DCLICK, self.OnItemDoubleClick)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self.list)
        self.Bind(wx.EVT_SHOW, self.OnShow)

        if self.hideClock:
            self.setClockButton.Hide()
        else:
            self.Bind(wx.EVT_BUTTON, self.setClocks, id=self.ID_SET_TIME)

        if self.hideRecord:
            self.recordButton.Hide()
        else:
            self.Bind(wx.EVT_BUTTON, self.startRecording, id=self.ID_START_RECORDING)

        self.Bind(EVT_RECORD_BUTTON, self.startRecording)

        if not self.showWarnings:
            self.infoText.Hide()

        # For doing per-item tool tips in the list
        self.lastToolTipItem = -1
        self.list.Bind(wx.EVT_MOTION, self.OnListMouseMotion)
        self.list.Bind(wx.EVT_LEAVE_WINDOW, self.OnExitWindow)

        # Manual tool tip generation (ULC tooltips seem broken)
        self.tooltipFrame = DeviceToolTip(self) if tooltips else None

        self.updateTimerCalls = 0
        self.updateTimer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.UpdateTimerHandler, self.updateTimer)


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

        # XXX: TEST - DELETE!
        self.iconcycle = cycle((self.ICON_CONNECTION_MSD,
                                self.ICON_CONNECTION_USB,
                                self.ICON_CONNECTION_WIFI))
        self.statuscycle = cycle((self.ICON_NONE,
                                  self.ICON_INFO,
                                  self.ICON_WARN,
                                  self.ICON_ERROR))

        return images


    def UpdateTimerHandler(self, _evt=None):
        """ Handle timer 'tick' by refreshing device list.
        """
        self.updateTimerCalls += 1

        if deviceChanged(recordersOnly=False):
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROWWAIT))
            newPaths = tuple(getDeviceList())
            if newPaths == self.recorderPaths:
                self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
                return
            self.recorderPaths = newPaths
            self.populateList()
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            return

        # Update currently displayed devices less frequently. Adjust later?
        if self.updateTimerCalls % 4 == 0:
            if self.batteryCol is not None:
                self.updateBatteryDisplay()
            if self.buttonCol is not None:
                self.updateButtonDisplay()
            if self.statusCol is not None:
                self.updateStatusDisplay()


    def getConnectionIcon(self, dev):
        """ Get the index of the appropriate connection type icon.
        """
        # XXX: REMOVE - Test of different icons
        # if dev.productName.startswith('W'):
        #     return self.ICON_CONNECTION_WIFI

        if GUI_DEMO:
            return next(self.iconcycle)

        # This is a primitive mechanism based on the `ConfigInterface`
        # subclass name. Also, all but USB are currently hypothetical.
        configname = dev.config.__class__.__name__.lower()
        if dev.available:
            return self.ICON_CONNECTION_MSD
        if 'file' in configname or 'serial' in configname:
            return self.ICON_CONNECTION_USB
        elif 'wifi' in configname:
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

        if os.path.exists(dev.path):
            freeSpace = os_specific.getFreeSpace(dev.path) / 1048576
            if freeSpace < SPACE_WARN_MB:
                tip = f"This device is nearly full ({freeSpace:.2f} MB available)."
                icon = self.ICON_INFO
                if freeSpace < SPACE_MIN_MB:
                    tip += " This may prevent configuration."
                    icon = self.ICON_ERROR
                tips.append(tip)

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

        if len(tips) == 0:
            self.listToolTips[index] = None
            self.listMsgs[index] = None
            return

        # XXX: REMOVE
        if GUI_DEMO:
            icon = next(self.statuscycle)

        if self.showConnection:
            self.list.SetItemImage(index, [icon, self.getConnectionIcon(dev)])
        else:
            self.list.SetItemImage(index, [icon])

        self.listToolTips[index] = '\n'.join(tips)
        self.listMsgs[index] = '\n'.join([f'\u2022 {s}' for s in tips])


    def populateList(self):
        """ Find recorders and add them to the list.
        """
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))

        self.list.ClearAll()
        self.recorders.clear()
        self.itemDataMap.clear()

        for i, c in enumerate(self.columns):
            self.list.InsertColumn(i, c[0])

        self.minWidths = [self.list.GetTextExtent(c.name)[0] + 4 for c in self.columns]

        if self.batteryCol is not None:
            self.minWidths[self.batteryCol] = 40

        # This is to provide tool tips for individual list rows
        self.listMsgs = [None] * len(self.recorderPaths)
        self.listToolTips = [None] * len(self.recorderPaths)

        index = None
        for idx, dev in enumerate(filter(self.filter, getDevices())):
            try:
                index = self.list.InsertImageStringItem(idx, dev.path, [0], int(self.checks))
                self.itemDataMap[index] = [dev.path]
                self.recorders[index] = dev
                for i, col in enumerate(self.columns[1:], 1):
                    val = col.formatter(dev, index, i, self)  # populates item and returns data map value
                    self.itemDataMap[index].append('' if val is None else val)
                    self.list.SetColumnWidth(i, wx.LIST_AUTOSIZE)

                self.list.SetItemData(index, index)

                if self.showWarnings:
                    self.setItemIcon(index, dev)

            except IOError:
                # XXX: Catch new endaq.device exceptions?
                wx.MessageBox(
                    f"An error occurred while trying to access a recorder ({dev.path})."
                    "\n\nThe device's configuration data may be damaged. "
                    "Try disconnecting and reconnecting the device.",
                    "Device Error", parent=self)
                if index is not None:
                    self.list.DeleteItem(index)

        for i, w in enumerate(self.minWidths):
            w = w + 8
            if self.list.GetColumnWidth(i) < w:
                self.list.SetColumnWidth(i, w)
            self.listWidth += self.list.GetColumnWidth(i)

        # if self.batteryCol is not None:
        #     self.list.SetColumnWidth(self.batteryCol, self.minWidths[self.batteryCol])

        if not self.recorders or not self.selected:
            self.OnItemDeselected(None)

        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    def getSelected(self):
        """ Get the device corresponding to the selected item in the list.
        """
        if self.selected is None:
            return None
        return self.recorders.get(self.selected, None)


    def updateBatteryDisplay(self):
        """ Update the battery level icons.
        """
        for index, dev in self.recorders.items():
            populateBatteryColumn(dev, index, self.batteryCol, self)


    def updateButtonDisplay(self):
        # TODO: Update buttons (validate, etc.)
        pass


    def updateStatusDisplay(self):
        for index, dev in self.recorders.items():
            populateStatusColumn(dev, index, self.statusCol, self)


    def OnColClick(self, evt):
        # Required by ColumnSorterMixin
        evt.Skip()


    def OnItemSelected(self, evt):
        """ Handle list item (row) selection.
        """
        self.selected = self.list.GetItemData(evt.Index)
        if self.listMsgs[self.selected] is not None:
            self.infoText.SetLabel(self.listMsgs[self.selected])
        self.okButton.Enable(True)

        recorder = self.recorders.get(self.selected, None)
        if recorder.canRecord:
            self.recordButton.SetToolTip(self.RECORD_ENABLED)
            self.recordButton.Enable(True)
        else:
            self.recordButton.SetToolTip(self.RECORD_UNSUPPORTED)
            self.recordButton.Enable(False)

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
        if not self.recorders or not self.tooltipFrame:
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
                self.updateTimer.Start(self.autoUpdate)
        else:
            self.updateTimer.Stop()
            if self.tooltipFrame:
                self.tooltipFrame.timer.Stop()
                self.tooltipFrame.Hide()
        evt.Skip()
        

    def setClocks(self, _evt=None):
        """ Set all clocks. Used as an event handler.
        """
        fails = []
        butts = self.okButton, self.cancelButton, self.setClockButton
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        for b in butts:
            b.Enable(False)

        timerRunning = self.updateTimer.IsRunning()
        self.updateTimer.Stop()

        for rec in self.recorders.values():
            try:
                rec.setTime()
            except Exception as err:
                name = f"{rec.productName} SN:{rec.serial} ({rec.path})"
                fails.append(name)
                logger.error(f"{type(err)} setting clock on {name}: {err}")

        for b in butts:
            b.Enable(True)

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

        if timerRunning:
            self.updateTimer.Start(self.autoUpdate)

        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    def startRecording(self, _evt=None):
        """ Initiate a recording.
        """
        # XXX:
        print('start recording')
        return

        timerRunning = self.updateTimer.IsRunning()
        self.updateTimer.Stop()

        try:
            recorder = self.recorders.get(self.selected, None)
            if recorder and recorder.canRecord:
                recorder.startRecording()
        finally:
            if timerRunning:
                self.updateTimer.Start(self.autoUpdate)


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
