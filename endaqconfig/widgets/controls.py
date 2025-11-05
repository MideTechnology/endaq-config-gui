"""
Device control buttons and column population/content formatting.
"""
import logging
import os.path
from time import time

import wx
from wx.lib.agw import ultimatelistctrl as ULC
# import wx.lib.platebtn as platebtn

from endaq.device.response_codes import DeviceStatusCode
from endaq.device import CommandError, UnsupportedFeature, Recorder
from endaq.device.command_interfaces import SerialCommandInterface

from . import battery_icons
from .events import EvtConfigButton, EvtRecordButton, EvtStreamButton, EvtLockDevice, EvtBlink
from ..common import deviceString

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .device_dialog import DeviceSelectionDialog


logger = logging.getLogger(__name__)


# ===========================================================================
#
# ===========================================================================

# Text colors for the Status column
# If status >= 200, use status % 100.
STATUS_COLORS = {
    0: None,  # Idle
    10: wx.BLUE,  # Recording
    20: wx.Colour(0, 200, 0),  # Reset pending
    30: wx.Colour(0, 200, 0),  # Start Pending
    31: wx.BLUE,  # Stopping recording
    40: wx.Colour(0, 200, 0),  # Triggering
    50: wx.BLUE,  # Uploading
    100: wx.Colour(200, 200, 200),  # Sleeping
    101: wx.Colour(200, 200, 200),  # Waking
    110: wx.Colour(200, 200, 200),  # Going offline
    -10: wx.RED  # Error (default for all negative status codes)
}

# Status text
# DeviceStatusCode seems to get cast to int, so enum names not available
# If status >= 200, use status % 100.
STATUS_TEXT = {
    -110: "Disconnected",
    -10: "Error",
    0: "Ready",
    1: "Ready",
    10: "Recording",
    20: "Resetting",
    29: "Updating",  # Not a real code, replace if added or number reused
    30: "Starting",
    31: "Stopping",
    40: "Triggering",
    50: "Uploading",
    60: "Streaming",
    100: "Sleeping",
    101: "Waking",
    110: "Offline",
}

# Status text
# Longer forms of some STATUS_TEXT, used where there's more space
# TODO: Use this in tooltips!
STATUS_TOOLTIP = {
    0: "Ready",
    29: "Updating Software",  # Not a real code, replace if added or number reused
    30: "Starting Recording",
    31: "Stopping Recording",
    40: "Awaiting Trigger",
    50: "Uploading to Cloud",
}


def getStatusTooltip(status: DeviceStatusCode):
    displayCode = status if status in STATUS_TEXT else (status // 10) * 10
    if displayCode in STATUS_TOOLTIP:
        return STATUS_TOOLTIP[displayCode]
    elif displayCode in STATUS_TEXT:
        return STATUS_TEXT[displayCode]
    return f'DeviceStatusCode {status}'


# ===========================================================================
#
# ===========================================================================

class NewControlButtons(wx.Panel):
    """
    Panel containing device control buttons (start/stop recording and config).
    """

    BG_NORMAL = None  # Taken from widget's defaults
    FG_NORMAL = None

    ICONS = None  # class variable, a list of icons, set on first use


    def __init__(self, root, parent, device, index, column,
                 showConfig=True):
        """
        Panel containing device control buttons (start/stop recording and
        config).

        :param root: The dialog root.
        :param parent: The parent widget (the list control).
        :param device: The corresponding recorder for this row.
        :param index: The index of the row in the list.
        :param column: The list control column index.
        :param showConfig: If `True`, show the configuration button.
            Not yet supported!
        """
        super().__init__(parent, -1)
        self.root = root
        self.list = parent
        self.device = device
        self.index = index
        self.column = column

        self.recording = False
        self.uploading = False

        bg = parent.GetBackgroundColour()
        self.SetBackgroundColour(bg)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(sizer)

        self.addButtons(sizer, showConfig)
        self.updateButtons()

        sizer.Fit(self)


    @classmethod
    def _loadImages(cls):
        """
        TEST. Reads icons from a PNG for easy iteration. Replace with hard-coded converted images later.
        """
        if cls.ICONS is None:

            filename = os.path.join(os.path.dirname(__file__), 'control_buttons.png')
            img = wx.Image(filename, wx.BITMAP_TYPE_PNG)

            numIcons = 7
            size = img.GetWidth() // numIcons
            cls.ICONS = []
            for col in range(numIcons):
                cls.ICONS.append([img.GetSubImage(wx.Rect(col * size, row * size, size, size)).ConvertToBitmap()
                                  for row in range(4)])


    def addButtons(self, sizer: wx.Sizer, showConfig: bool):
        """ Add the buttons to the panel.

            :param sizer: The containing sizer.
            :param showConfig: If `True`, show the configuration button.
        """
        self._loadImages()
        (self.configIcons, self.recordIcons, self.stopIcons, self.streamIcons,
         self.streamingIcons, self.lockIcons, self.lockedIcons) = self.ICONS

        size = self.configIcons[0].GetSize()
        style = wx.NO_BORDER | wx.BU_EXACTFIT

        def _add(icons, tooltip, handler):
            """ Helper to do the button-adding busy work. """
            btn = wx.BitmapButton(self, -1, icons[0], style=style, size=size)
            btn.SetBitmapCurrent(icons[1])
            btn.SetBitmapPressed(icons[2])
            btn.SetBitmapDisabled(icons[3])
            btn.SetBackgroundColour(self.GetBackgroundColour())
            btn.SetToolTip(tooltip)
            sizer.Add(btn, 1, wx.EXPAND)
            btn.Bind(wx.EVT_BUTTON, handler)
            return btn

        self.stopBtn = _add(self.stopIcons, 'Stop Recording/Streaming', self.OnStopButton)
        self.recBtn = _add(self.recordIcons, 'Start Recording', self.OnRecordButton)
        self.streamBtn = _add(self.streamIcons, 'Start Streaming', self.OnStreamButton)
        self.configBtn = _add(self.configIcons, 'Configure Device', self.OnConfigButton)
        self.lockBtn = _add(self.lockIcons, 'Set Device Lock', self.OnLockButton)

        self.stopBtn.Enable(False)
        self.streamBtn.Enable(self.device.command.canStream)
        self.lockBtn.Enable('MQTT' in type(self.device.command).__name__)
        self.configBtn.Show(showConfig)

        if self.BG_NORMAL is None:
            self.__class__.BG_NORMAL = self.recBtn.GetBackgroundColour()
            self.__class__.FG_NORMAL = self.recBtn.GetForegroundColour()


    def updateLock(self):
        if 'MQTT' not in type(self.device.command).__name__:
            self.lockBtn.Enable(False)
            self.lockBtn.UnsetToolTip()
            return

        locked, mine = self.device.command.isLocked()

        icons = self.lockedIcons if locked and not mine else self.lockIcons
        self.lockBtn.SetBitmap(icons[0])
        if not locked:
            self.lockBtn.SetBitmapCurrent(icons[1])
            self.lockBtn.SetBitmapPressed(icons[2])
            self.lockBtn.SetBitmapDisabled(icons[3])
        else:
            self.lockBtn.SetBitmapCurrent(icons[0])
            self.lockBtn.SetBitmapPressed(icons[0])
            self.lockBtn.SetBitmapDisabled(icons[0])

            # self.lockBtn.Enable(mine or not locked)

        if mine:
            self.lockBtn.SetToolTip('You have control of this device\nClick to release lock')
        elif locked:
            self.lockBtn.SetToolTip('This device has been locked by another user')
        else:
            self.lockBtn.SetToolTip('Device unlocked (available)\nClick to set lock')


    def updateButtons(self, enabled=True):
        """ Update the button labels, tooltips, and enabled/disabled state.
        """
        try:
            status = self.device.command.status[1]
            if status and status >= 200:
                status %= 100
        except (AttributeError, CommandError, UnsupportedFeature):
            status = None

        self.recording = status in (DeviceStatusCode.START_PENDING,
                                    DeviceStatusCode.RECORDING,
                                    DeviceStatusCode.STREAMING,
                                    DeviceStatusCode.TRIGGERING)
        self.uploading = status == DeviceStatusCode.UPLOADING

        self.recBtn.Show(self.device.command.canRecord)
        self.recBtn.Enable(enabled
                           and self.device.command.canRecord
                           and not self.uploading)

        if self.configBtn.IsShown():
            self.configBtn.Enable(enabled
                                  and self.device.hasConfigInterface
                                  and self.device.config.available
                                  and not self.uploading
                                  and not self.recording)

        # TODO: Redo this logic?
        self.stopBtn.Enable(self.recording and not self.uploading)
        self.recBtn.Enable(not self.recording and not self.uploading)

        self.updateLock()


    def _postEvent(self, event):
        """ Helper to post events generated by list item control buttons.
        """
        try:
            self.list.Select(self.index)
            wx.PostEvent(self.root, event)
        except RuntimeError:
            # Dialog probably closed during scan, which is okay.
            pass


    # =======================================================================
    #
    # =======================================================================

    def OnRecordButton(self, evt):
        """ Handle Start Recording button press.
        """
        self._postEvent(EvtRecordButton(device=self.device, stop=False))


    def OnStopButton(self, evt):
        """ Handle Stop Recording button press.
        """
        self._postEvent(EvtRecordButton(device=self.device, stop=True))


    def OnConfigButton(self, evt):
        """ Handle Configure button press.
        """
        self._postEvent(EvtConfigButton(device=self.device))


    def OnStreamButton(self, _evt):
        """ Handle Stream button press.
        """
        self._postEvent(EvtStreamButton(device=self.device))


    def OnLockButton(self, _evt):
        """ Handle Lock button press.
        """
        locked, mine = self.device.command.isLocked()
        self._postEvent(EvtLockDevice(device=self.device,
                                      clear=locked,
                                      force=wx.GetKeyState(wx.WXK_CONTROL)))


# ===========================================================================
#
# ===========================================================================

class ListContextMenu(wx.Menu):
    """ 'Right Click' menu for devlice list items. Duplicates most of the
        functionality of the item control buttons.
    """

    def _addMI(self, label, handler, helpString='', kind=wx.ITEM_NORMAL):
        """ Helper to simplify adding list items. """
        mi = self.Append(wx.ID_ANY, label, helpString, kind)
        self.Bind(wx.EVT_MENU, handler, id=mi.GetId())
        return mi


    def __init__(self, root, device, devlist, index):
        """ 'Right Click' menu for devlice list items.
        """
        self.root = root
        self.list = devlist
        self.device = device
        self.index = index
        super().__init__()

        devstr = deviceString(self.device)
        config = self._addMI(f"Configure {devstr}...", self.OnConfig)
        startRec = self._addMI(f"Start Recording", self.OnStartRecording)
        startStream = self._addMI(f"Start Streaming", self.OnStartStreaming)
        stopRec = self._addMI("Stop Recording/Streaming", self.OnStopRecording)
        self.AppendSeparator()
        lock = self._addMI(f"Lock {devstr}", self.OnLock)
        self.AppendSeparator()
        blink = self._addMI("Blink Recorder LEDs", self.OnBlink)

        locked, mine = self.device.command.isLocked()
        anothers = locked and not mine

        isRecording = self.device.command.status[1] in (DeviceStatusCode.RECORDING,
                                                        DeviceStatusCode.RECORDING_PERIODIC,
                                                        DeviceStatusCode.TRIGGERING,
                                                        DeviceStatusCode.TRIGGERING_PERIODIC,
                                                        DeviceStatusCode.STREAMING)

        config.Enable(not anothers)
        startRec.Enable(self.device.command.canRecord and not anothers and not isRecording)
        startStream.Enable(self.device.command.canStream and not anothers and not isRecording)
        stopRec.Enable(not anothers and isRecording)
        blink.Enable(isinstance(self.device.command, SerialCommandInterface))

        self.clearLock = locked
        self.forceLock = anothers and wx.GetKeyState(wx.WXK_CONTROL)
        lock.Enable(not locked or mine or self.forceLock)

        if mine:
            lock.SetItemLabel(f'Unlock {devstr}')
        elif self.forceLock:
            lock.SetItemLabel(f"Force clear lock on {devstr}")


    def _postEvent(self, event):
        try:
            self.list.Select(self.index)
            wx.PostEvent(self.root, event)
        except RuntimeError:
            # Dialog probably closed while processing, which is okay.
            pass

    def OnStartRecording(self, evt):
        """ Handle Start Recording menu item.
        """
        self._postEvent(EvtRecordButton(device=self.device, stop=False))


    def OnStartStreaming(self, evt):
        """ Handle Start Recording menu item.
        """
        self._postEvent(EvtStreamButton(device=self.device))


    def OnStopRecording(self, evt):
        """ Handle Stop Recording menu item.
        """
        self._postEvent(EvtRecordButton(device=self.device, stop=True))


    def OnConfig(self, evt):
        """ Handle Configure menu item.
        """
        self._postEvent(EvtConfigButton(device=self.device))


    def OnLock(self, _evt):
        """ Handle Lock menu item.
        """
        self._postEvent(EvtLockDevice(device=self.device,
                                      clear=self.clearLock,
                                      force=self.forceLock))


    def OnBlink(self, evt):
        """ Handle Blink menu item.
        """
        self._postEvent(EvtBlink(device=self.device))


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
    pan = NewControlButtons(root, root.list, dev, index, column)
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
        batStat = dev.command._battery[1]
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
        _, code, msg = dev.command.status
        code = code or DeviceStatusCode.IDLE
    except (AttributeError, UnsupportedFeature):
        code, msg = DeviceStatusCode.IDLE, ''

    if dev.hasCommandInterface and 'MQTT' not in str(dev.command) and not dev.command.available:
        t, cmd = dev.command.lastCommand
        cmd = (cmd or {}).get('EBMLCommand', {})
        if cmd and t < time() + 45:
            if 'RecStart' in cmd:
                code, msg = DeviceStatusCode.START_PENDING, ''
            elif 'RecStop' in cmd:
                code, msg = DeviceStatusCode.STOP_PENDING, ''
            elif 'Reset' in cmd:
                code, msg = DeviceStatusCode.RESET_PENDING, ''
            elif 'FlashPackage' or 'SecureUpdateAll' in cmd:
                # An update command. No DeviceStatusCode for 'upload pending'
                # but there is one in STATUS_TEXT. Replace if one gets
                # added to the DeviceStatusCode enum.
                code, msg = 29, ''
            elif any(k.startswith('Legacy') for k in cmd):
                # Legacy update command. See above.
                code, msg = 29, ''

        # print(dev, cmd, code)

    # Find specific color, or round to lowest multiple of 10
    displayCode = code if code in STATUS_COLORS else (code // 10) * 10
    color = STATUS_COLORS.get(displayCode, None)
    text = STATUS_TEXT.get(displayCode, "")

    if code < 0:
        color = color or STATUS_COLORS.get(-10)
        text = text or STATUS_TEXT.get(-10)

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
