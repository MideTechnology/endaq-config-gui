"""
Device control buttons and column population/content formatting.
"""

import wx
from wx.lib.agw import ultimatelistctrl as ULC

from endaq.device.response_codes import DeviceStatusCode
from endaq.device import CommandError, UnsupportedFeature, Recorder

from . import battery_icons
from .events import EvtConfigButton, EvtRecordButton

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .device_dialog import DeviceSelectionDialog


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

        self.updateButtons()


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


    def updateButtons(self, enabled=True):
        """ Update the button labels, tooltips, and enabled/disabled state.
        """
        try:
            status = self.device.command.status[0]
        except (AttributeError, CommandError, UnsupportedFeature):
            status = None

        self.recording = status == DeviceStatusCode.RECORDING
        self.uploading = status == DeviceStatusCode.UPLOADING


        self.recBtn.Show(self.device.canRecord)
        self.recBtn.Enable(enabled
                           and self.device.canRecord
                           and not self.uploading)

        self.configBtn.Enable(enabled
                              and self.device.hasConfigInterface
                              and self.device.config.available
                              and not self.uploading
                              and not self.recording)

        if self.recording:
            self.recBtn.SetLabel("Stop Recording")
            self.recBtn.SetToolTip(self.STOP_TT)
            self.recBtn.SetBackgroundColour(self.BG_RECORDING)
            self.recBtn.SetForegroundColour(self.FG_RECORDING)
        else:
            self.recBtn.SetLabel("Start Recording")
            self.recBtn.SetToolTip(self.START_TT)
            self.recBtn.SetBackgroundColour(self.BG_NORMAL)
            self.recBtn.SetForegroundColour(self.FG_NORMAL)


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
    pan = ControlButtons(root, root.list, dev, index, column)
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

