"""
Device control buttons.

Two and a half versions:
    1. Normal buttons
    2. Standard wxPython BitmapButtons
    2½. wxPython PlateButtons
"""

import wx

from endaq.device.response_codes import DeviceStatusCode
from endaq.device import CommandError, UnsupportedFeature

from .events import EvtConfigButton, EvtRecordButton


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
        self.recBtn.Enable(enabled and self.device.canRecord)
        self.configBtn.Enable(enabled
                              and self.device.hasConfigInterface
                              and self.device.config.available)

        try:
            status = self.device.command.status[0]
        except (AttributeError, CommandError, UnsupportedFeature):
            status = None

        self.recording = status == DeviceStatusCode.RECORDING

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
