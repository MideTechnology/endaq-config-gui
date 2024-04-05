"""
Device control buttons.

Two and a half versions:
    1. Normal buttons
    2. Standard wxPython BitmapButtons
    2½. wxPython PlateButtons
"""

import wx
import wx.lib.platebtn as pb

from endaq.device.response_codes import DeviceStatusCode
from endaq.device import CommandError, UnsupportedFeature

from .icons import button_config, button_record, button_stop
from .events import EvtConfigButton, EvtRecordButton


class ControlButtons(wx.Panel):
    """
    Panel containing device control buttons (start/stop recording and config).
    """

    # Tooltip text
    START_TT = "Start the recording device"
    STOP_TT = "Stop the recording device"
    CONFIG_TT = "Configure the recording device"

    def __init__(self, root, parent, device, index, column,
                 showConfig=True):
        super().__init__(parent, -1)
        self.root = root
        self.list = parent
        self.device = device
        self.index = index
        self.column = column

        bg = parent.GetBackgroundColour()
        self.SetBackgroundColour(bg)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(sizer)

        self.addButtons(sizer, showConfig)
        self.recBtn.Bind(wx.EVT_BUTTON, self.OnRecordButton)
        self.configBtn.Bind(wx.EVT_BUTTON, self.OnConfigButton)

        sizer.Fit(self)

        self.recBtn.Enable(device.canRecord)
        self.configBtn.Enable(device.hasConfigInterface and device.config.available)


    def addButtons(self, sizer, showConfig):
        """ Add the button widgets to the panel.
        """
        self.recBtn = wx.Button(self, -1, "Start Recording", size=(-1, 22))
        sizer.Add(self.recBtn, 1, wx.EXPAND)

        self.configBtn = wx.Button(self, -1, "Configure", size=(-1, 22))
        sizer.Add(self.configBtn, 1, wx.EXPAND)

        self.configBtn.Show(showConfig)


    def updateButtons(self):
        """ Update the button labels, tooltips, and enabled/disabled state.
        """
        self.recBtn.Enable(self.device.canRecord)
        self.configBtn.Enable(self.device.hasConfigInterface
                              and self.device.config.available)

        try:
            status = self.device.command.status[0]
        except (AttributeError, CommandError, UnsupportedFeature):
            status = None

        if status == DeviceStatusCode.RECORDING:
            self.recBtn.SetLabel("Stop Recording")
            self.recBtn.SetToolTip(self.STOP_TT)
        else:
            self.recBtn.SetLabel("Start Recording")
            self.recBtn.SetToolTip(self.START_TT)


    def OnRecordButton(self, evt):
        """ Handle Start/Stop Recording button press.
        """
        try:
            self.list.Select(self.index)
            wx.PostEvent(self.root, EvtRecordButton(device=self.device))
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


class ControlImageButtons(ControlButtons):
    """
    Test panel with image buttons. Doesn't work right (yet).
    """

    ICON_CONFIG = None
    ICON_RECORD = None
    ICON_STOP = None

    def __init__(self, root, parent, device, index, column, showConfig=True, plates=False):
        self.USE_PLATES = plates
        super().__init__(root, parent, device, index, column, showConfig)


    def addButtons(self, sizer, showConfig):
        """ Add the button widgets to the panel.
        """
        self.loadIcons()
        if self.USE_PLATES:
            self.recBtn = pb.PlateButton(self, -1, bmp=self.ICON_RECORD[0], size=(32,24), style=pb.PB_STYLE_NOBG)
            self.configBtn = pb.PlateButton(self, -1, bmp=self.ICON_CONFIG[0], size=(32,24), style=pb.PB_STYLE_NOBG)
        else:
            self.recBtn = wx.BitmapButton(self, -1, self.ICON_RECORD[0], size=(24, 24), style=wx.NO_BORDER)
            self.configBtn = wx.BitmapButton(self, -1, self.ICON_CONFIG[0], size=(24, 24), style=wx.NO_BORDER)

        self.configBtn.Show(showConfig)
        sizer.Add(self.recBtn, 0, wx.EXPAND)
        sizer.Add(self.configBtn, 0, wx.EXPAND)

        bg = self.GetBackgroundColour()
        for btn, icons in ((self.recBtn, self.ICON_RECORD), (self.configBtn, self.ICON_CONFIG)):
            btn.SetBackgroundColour(bg)
            btn.SetBitmapFocus(icons[1])
            btn.SetBitmapDisabled(icons[3])

            if self.USE_PLATES:
                btn.SetBitmapSelected(icons[2])  # PlateButton only
            else:
                btn.SetBitmapPressed(icons[2])  # BitmapButton only

        self.recBtn.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)
        self.configBtn.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)

        self.recBtn.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseLeave)
        self.configBtn.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseLeave)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseLeave)


    @classmethod
    def loadIcons(cls):
        if cls.ICON_CONFIG:
            return

        cls.ICON_CONFIG = [img.GetBitmap() for img in button_config]
        cls.ICON_RECORD = [img.GetBitmap() for img in button_record]
        cls.ICON_STOP = [img.GetBitmap() for img in button_stop]


    def OnMouseLeave(self, evt):
        # XXX: Still doesn't update right
        self.recBtn.Update()
        self.configBtn.Update()
        self.Update()
        evt.Skip()


    def updateButtons(self):
        self.recBtn.Enable(self.device.canRecord)
        self.configBtn.Enable(self.device.hasConfigInterface
                              and self.device.config.available)

        try:
            status = self.device.command.status[0]
        except (AttributeError, CommandError, UnsupportedFeature):
            status = None

        if status == DeviceStatusCode.RECORDING:
            icons = self.ICON_STOP
            self.recBtn.SetToolTip(self.STOP_TT)
        else:
            icons = self.ICON_RECORD
            self.recBtn.SetToolTip(self.START_TT)

        self.recBtn.SetBitmapFocus(icons[1])
        self.recBtn.SetBitmapDisabled(icons[3])

        if self.USE_PLATES:
            self.recBtn.SetBitmapSelected(icons[2])  # PlateButton only
        else:
            self.recBtn.SetBitmapPressed(icons[2])  # BitmapButton only

        # TODO: Change icon if recording