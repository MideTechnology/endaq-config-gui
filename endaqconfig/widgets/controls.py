"""
Device control buttons and column population/content formatting.
"""
import os.path
from time import time

import wx
from wx.lib.agw import ultimatelistctrl as ULC
import wx.lib.platebtn as platebtn

from endaq.device.response_codes import DeviceStatusCode
from endaq.device import CommandError, UnsupportedFeature, Recorder

from . import battery_icons
from .events import EvtConfigButton, EvtRecordButton

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .device_dialog import DeviceSelectionDialog


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
    29: "Updating Software",  # Not a real code, replace if added or number reused
    30: "Starting Recording",
    31: "Stopping Recording",
    40: "Awaiting Trigger",
    50: "Uploading to Cloud",
}

# ===========================================================================
#
# ===========================================================================


class ControlButtons(wx.Panel):
    """
    Panel containing device control buttons (start/stop recording and config).
    """

    # Tooltip text
    START_TT = "Start the recording device"
    STOP_TT = "Stop the recording device"
    CONFIG_TT = "Configure the recording device"

    BG_NORMAL = None  # Taken from widget's defaults
    FG_NORMAL = None
    BG_RECORDING = wx.RED
    FG_RECORDING = wx.WHITE

    def __init__(self, root, parent, device, index, column,
                 showConfig=False):
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
        self.recBtn.Bind(wx.EVT_BUTTON, self.OnRecordButton)
        self.configBtn.Bind(wx.EVT_BUTTON, self.OnConfigButton)

        sizer.Fit(self)

        # updateList should do this
        # self.updateButtons()


    def addButtons(self, sizer, showConfig):
        """ Add the button widgets to the panel.
            (Isolated for easy experiments with alternative subclasses.)
        """
        self.recBtn = wx.Button(self, -1, "Start Recording", size=(-1, 22))
        sizer.Add(self.recBtn, 1, wx.EXPAND)

        self.configBtn = wx.Button(self, -1, "Configure", size=(-1, 22))
        sizer.Add(self.configBtn, 1, wx.EXPAND)

        if self.BG_NORMAL is None:
            self.__class__.BG_NORMAL = self.recBtn.GetBackgroundColour()
            self.__class__.FG_NORMAL = self.recBtn.GetForegroundColour()

        self.configBtn.Show(showConfig)


    def _setRecButton(self, label, tooltip, bg, fg):
        if label:
            self.recBtn.SetLabel(label)
        self.recBtn.SetToolTip(tooltip or '')
        if bg is not None:
            self.recBtn.SetBackgroundColour(bg)
        if fg is not None:
            self.recBtn.SetForegroundColour(fg)


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

        self.recBtn.Show(self.device.canRecord)
        self.recBtn.Enable(enabled
                           and self.device.canRecord
                           and not self.uploading)

        if self.configBtn.IsShown():
            self.configBtn.Enable(enabled
                                  and self.device.hasConfigInterface
                                  and self.device.config.available
                                  and not self.uploading
                                  and not self.recording)

        if self.recording:
            label = ("Stop Streaming" if status == DeviceStatusCode.STREAMING
                     else "Stop Recording")
            self._setRecButton(label, self.STOP_TT,
                               self.BG_RECORDING, self.FG_RECORDING)
        else:
            self._setRecButton("Start Recording", self.START_TT,
                               self.BG_NORMAL, self.FG_NORMAL)


    def OnRecordButton(self, evt):
        """ Handle Start/Stop Recording button press.
        """
        try:
            self.list.Select(self.index)
            wx.PostEvent(self.root, EvtRecordButton(device=self.device,
                                                    stop=self.recording))
            evt.Skip()
        except RuntimeError:
            # Dialog probably closed during scan, which is okay.
            pass


    def OnConfigButton(self, evt):
        """ Handle Configure button press.
        """
        try:
            self.list.Select(self.index)
            wx.PostEvent(self.root, EvtConfigButton(device=self.device))
            evt.Skip()
        except RuntimeError:
            # Dialog probably closed during scan, which is okay.
            pass


# ===========================================================================

class NewControlButtons(ControlButtons):

    def _loadImages(self):
        """
        TEST. Reads icons from a PNG for easy iteration. Replace with hard-coded converted images later.
        """
        filename = os.path.join(os.path.dirname(__file__), 'control_buttons.png')
        img = wx.Image(filename, wx.BITMAP_TYPE_PNG)

        numIcons = 7
        size = img.GetWidth() // numIcons
        icons = []
        for col in range(numIcons):
            icons.append([img.GetSubImage(wx.Rect(col * size, row * size, size, size)).ConvertToBitmap() for row in range(4)])

        self.configIcons, self.recordIcons, self.stopIcons, self.streamIcons, self.streamingIcons, self.lockIcons, self.lockedIcons = icons
        self.icons = icons


    def addButtons(self, sizer, showConfig):
        """
        """
        self._loadImages()
        size = self.configIcons[0].GetSize()
        style = wx.NO_BORDER | wx.BU_EXACTFIT

        def _add(icons, tooltip):
            btn = wx.BitmapButton(self, -1, icons[0], style=style, size=size)
            btn.SetBitmapCurrent(icons[1])
            btn.SetBitmapPressed(icons[2])
            btn.SetBitmapDisabled(icons[3])
            btn.SetBackgroundColour(self.GetBackgroundColour())
            btn.SetToolTip(tooltip)
            sizer.Add(btn, 1, wx.EXPAND)
            return btn

        self.stopBtn = _add(self.stopIcons, 'Stop Recording/Streaming')
        self.recBtn = _add(self.recordIcons, 'Start Recording')
        self.streamBtn = _add(self.streamIcons, 'Start Streaming')
        self.configBtn = _add(self.configIcons, 'Configure Device')
        self.lockBtn = _add(self.lockIcons, 'Set Device Lock')

        self.stopBtn.Enable(False)
        if not self.device.isRemote:
            self.streamBtn.Enable(False)

        if 'MQTT' not in type(self.device.command).__name__:
            self.lockBtn.Enable(False)

        if self.BG_NORMAL is None:
            self.__class__.BG_NORMAL = self.recBtn.GetBackgroundColour()
            self.__class__.FG_NORMAL = self.recBtn.GetForegroundColour()


    def updateLock(self):
        lockId = self.device.command.lockId[1]
        locked = lockId and any(lockId)

        icons = self.lockedIcons if locked else self.lockIcons
        self.lockBtn.SetBitmap(icons[0])
        self.lockBtn.SetBitmapCurrent(icons[1])
        self.lockBtn.SetBitmapPressed(icons[2])
        self.lockBtn.SetBitmapDisabled(icons[3])


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

        print(dev, cmd, code)

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
