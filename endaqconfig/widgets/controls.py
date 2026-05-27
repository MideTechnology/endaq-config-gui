"""
Device control buttons and column population/content formatting.
"""
import logging
import os.path
from time import time
from typing import Optional, Union

import wx
from wx.lib.agw import ultimatelistctrl as ULC

from endaq.device.response_codes import DeviceStatusCode
from endaq.device import CommandError, UnsupportedFeature, Recorder
from endaq.device.command_interfaces import SerialCommandInterface

from . import battery_icons
from . import icons
from .events import EvtConfig, EvtRecord, EvtStream, EvtLockDevice, EvtBlink
from ..common import deviceString
from .threads import isOnline

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .device_dialog import DeviceSelectionDialog


logger = logging.getLogger(__name__)


# ===========================================================================
#
# ===========================================================================

# Status display: (list column text, list text color, tooltip text).
# `None` for color uses default. `None` for tooltip uses list column text.
# Note that some codes are for display and may not be in `DeviceStatusCode` (e.g. 29).
# If status >= 200, use status % 100.
STATUS_DISPLAY = {
    -110: ("Disconnected",  wx.RED,                     None),
    -10:  ("Error",         wx.RED,                     None),  # Also default for other errors
    0:    ("Ready",         None,                       None),
    1:    ("Ready",         None,                       None),
    10:   ("Recording",     wx.BLUE,                    "Recording/Streaming"),
    20:   ("Resetting",     wx.Colour(0, 200, 0),       None),
    29:   ("Updating",      wx.Colour(0, 200, 0),       "Updating Software"),
    30:   ("Starting",      wx.Colour(0, 200, 0),       "Starting Recording"),
    31:   ("Stopping",      wx.BLUE,                    "Stopping Recording"),
    40:   ("Triggering",    wx.Colour(0, 200, 0),       "Awaiting Trigger"),
    50:   ("Uploading",     wx.BLUE,                    "Uploading to Cloud"),
    60:   ("Streaming",     wx.BLUE,                    "Streaming Data"),
    100:  ("Sleeping",      wx.Colour(100, 100, 100),   None),
    101:  ("Waking",        wx.Colour(200, 200, 200),   None),
    110:  ("Offline",       wx.Colour(200, 200, 200),   None),
}


def getStatusDisplay(status: Union[DeviceStatusCode, int]) -> tuple[str, wx.Colour, str]:
    """ Get the 'status' list column contents/color and tooltip text. Unknown
        and special status codes are handled appropriately.
        
        :param status: Device status, as `DeviceStatusCode` or integer.
        :returns: Tuple of (column text, column text color, tooltip text).
            Color `None` means use efault.
    """
    if status in STATUS_DISPLAY:
        text, color, tooltip = STATUS_DISPLAY[status]
        return text, color, tooltip or text

    origStatus = status
    suffix = tipSuffix = ''

    if status >= 200:
        if status < 400:
            tipSuffix = ' (checking Wi-Fi periodically)'
        else:
            tipSuffix = ' (offline)'
        suffix = '*'
        status = status % 100

    if status not in STATUS_DISPLAY:
        status = -10 if status < 0 else (status // 10) % 10

    text, color, tooltip = STATUS_DISPLAY.get(status, (None, None, None))
    if text is None:
        text, tooltip = '', f'\u00ABDeviceStatusCode {origStatus}\u00BB'
    else:
        text, tooltip = f'{text}{suffix}', f'{tooltip or text}{tipSuffix}'

    return text, color, tooltip


# ===========================================================================
#
# ===========================================================================

class NewControlButtons(wx.Panel):
    """
    Panel containing device control buttons (start/stop recording and config).
    """

    BG_NORMAL = None  # Taken from widget's defaults
    FG_NORMAL = None

    ICONS: list = None  # class variable, a list of icons, set on first use


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

            # filename = os.path.join(os.path.dirname(__file__), 'control_buttons.png')
            # img = wx.Image(filename, wx.BITMAP_TYPE_PNG)

            img = icons.control_buttons.GetImage()

            numIcons = 10
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
         self.streamingIcons, self.lockIcons, self.lockedIcons, self.blinkIcons) = self.ICONS

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

        icons = self.lockedIcons if locked else self.lockIcons
        self.lockBtn.SetBitmap(icons[0])
        if not locked or mine:
            self.lockBtn.SetBitmapCurrent(icons[1])
            self.lockBtn.SetBitmapPressed(icons[2])
            self.lockBtn.SetBitmapDisabled(icons[3])
        else:
            self.lockBtn.SetBitmapCurrent(icons[3])
            self.lockBtn.SetBitmapPressed(icons[3])
            self.lockBtn.SetBitmapDisabled(icons[3])

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

        self.Enable(enabled and not self.uploading)

        self.recBtn.Show(self.device.command.canRecord)
        self.recBtn.Enable(enabled
                           and self.device.command.canRecord)

        if self.configBtn.IsShown():
            self.configBtn.Enable(enabled
                                  and self.device.hasConfigInterface
                                  # and self.device.config.available
                                  and not self.recording)

        # TODO: Redo this logic?
        self.stopBtn.Enable(self.recording and not self.uploading)

        self.updateLock()


    def _postEvent(self, event):
        """ Helper to post events generated by list item control buttons.
        """
        self.list.Select(self.index)
        wx.PostEvent(self.root, event)


    # =======================================================================
    #
    # =======================================================================

    def OnRecordButton(self, _evt):
        """ Handle Start Recording button press.
        """
        self._postEvent(EvtRecord(device=self.device, stop=False))


    def OnStopButton(self, _evt):
        """ Handle Stop Recording button press.
        """
        self._postEvent(EvtRecord(device=self.device, stop=True))


    def OnConfigButton(self, _evt):
        """ Handle Configure button press.
        """
        self._postEvent(EvtConfig(device=self.device))


    def OnStreamButton(self, _evt):
        """ Handle Stream button press.
        """
        self._postEvent(EvtStream(device=self.device))


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

    def _addMI(self, label, handler, bitmap=None, helpString='', kind=wx.ITEM_NORMAL):
        """ Helper to simplify adding list items. """
        mi = self.Append(wx.ID_ANY, label, helpString, kind)
        if bitmap:
            mi.SetBitmap(bitmap)
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

        NewControlButtons._loadImages()
        icons = NewControlButtons.ICONS

        available = isOnline(device)
        devstr = deviceString(self.device)
        config = self._addMI(f"Configure {devstr}...", self.OnConfig, icons[0][0])
        startRec = self._addMI(f"Start Recording", self.OnStartRecording, icons[1][0])
        startStream = self._addMI(f"Start Streaming", self.OnStartStreaming, icons[4][0])
        stopRec = self._addMI("Stop Recording/Streaming", self.OnStopRecording, icons[2][0])
        self.AppendSeparator()
        lock = self._addMI(f"Lock {devstr}", self.OnLock, icons[6][0])
        self.AppendSeparator()
        blink = self._addMI("Blink Recorder LEDs", self.OnBlink, icons[7][0])

        locked, mine = self.device.command.isLocked()
        anothers = locked and not mine

        isRecording = self.device.command.status[1] in (DeviceStatusCode.RECORDING,
                                                        DeviceStatusCode.RECORDING_PERIODIC,
                                                        DeviceStatusCode.TRIGGERING,
                                                        DeviceStatusCode.TRIGGERING_PERIODIC,
                                                        DeviceStatusCode.STREAMING)

        config.Enable(available and not anothers)
        startRec.Enable(available and self.device.command.canRecord and not anothers and not isRecording)
        startStream.Enable(available and self.device.command.canStream and not anothers and not isRecording)
        stopRec.Enable(available and not anothers and isRecording)
        blink.Enable(available and isinstance(self.device.command, SerialCommandInterface))

        self.clearLock = locked
        self.forceLock = anothers and wx.GetKeyState(wx.WXK_CONTROL)
        lock.Enable(available and not locked or mine or self.forceLock)

        if locked:
            lock.SetBitmap(icons[5][0])

        if mine:
            lock.SetItemLabel(f'Unlock {devstr}')
        elif self.forceLock:
            lock.SetItemLabel(f"Force clear lock on {devstr}")


    def _postEvent(self, event):
        self.list.Select(self.index)
        wx.PostEvent(self.root, event)


    def OnStartRecording(self, _evt):
        """ Handle Start Recording menu item.
        """
        self._postEvent(EvtRecord(device=self.device, stop=False))


    def OnStartStreaming(self, _evt):
        """ Handle Start Recording menu item.
        """
        self._postEvent(EvtStream(device=self.device))


    def OnStopRecording(self, _evt):
        """ Handle Stop Recording menu item.
        """
        self._postEvent(EvtRecord(device=self.device, stop=True))


    def OnConfig(self, _evt):
        """ Handle Configure menu item.
        """
        self._postEvent(EvtConfig(device=self.device))


    def OnLock(self, _evt):
        """ Handle Lock menu item.
        """
        self._postEvent(EvtLockDevice(device=self.device,
                                      clear=self.clearLock,
                                      force=self.forceLock))


    def OnBlink(self, _evt):
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
    if column is None or not isOnline(dev):
        return ''

    batIcon, batDesc = 0, 'Battery state not reported'

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
        # Non-MQTT devices only report state when queried, and do not
        # report as many states. Base status on the last command sent.
        t, cmd = dev.command.lastCommand
        cmd = (cmd or {}).get('EBMLCommand', {})
        if cmd and t < time() + 45:
            if 'RecStart' in cmd:
                code, msg = DeviceStatusCode.START_PENDING, ''
            elif 'RecStop' in cmd:
                code, msg = DeviceStatusCode.STOP_PENDING, ''
            elif 'Reset' in cmd:
                code, msg = DeviceStatusCode.RESET_PENDING, ''
            elif 'FlashPackage' in cmd or 'SecureUpdateAll' in cmd:
                # An update command. No DeviceStatusCode for 'upload pending'
                # but there is one in STATUS_TEXT. Replace if one gets
                # added to the DeviceStatusCode enum.
                code, msg = 29, ''
            elif any(k.startswith('Legacy') for k in cmd):
                # Legacy update command. See above.
                code, msg = 29, ''

    if code == DeviceStatusCode.STREAMING:
        # Only show a device as 'streaming' if the stream is getting saved.
        if not dev.command.streaming():
            code = DeviceStatusCode.RECORDING

    text, color, _tooltip = getStatusDisplay(code)
    if not color:
        color = root.list.GetTextColour()

    root.list.SetStringItem(index, column, text)

    font = root.list.GetFont()
    item = root.list.GetItem(index, column)
    item.SetMask(ULC.ULC_MASK_FONTCOLOUR | ULC.ULC_MASK_FONT)
    item.SetTextColour(color)
    item.SetFont(font)
    root.list.SetItem(item)

    return code
