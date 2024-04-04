"""

"""

import wx
import wx.lib.platebtn as platebtn

from .icons import button_config, button_record, button_stop

class ControlButtons(wx.Panel):

    ICON_CONFIG = None
    ICON_RECORD = None
    ICON_STOP = None

    def __init__(self, parent, device):
        super().__init__(parent, -1)
        self.device = device

        self.loadIcons()
        bg = parent.GetBackgroundColour()
        self.SetBackgroundColour(bg)

        self.recBtn = platebtn.PlateButton(self, -1, bmp=self.ICON_RECORD[0], size=(32,24), style=platebtn.PB_STYLE_NOBG)
        self.configBtn = platebtn.PlateButton(self, -1, bmp=self.ICON_CONFIG[0], size=(32,24), style=platebtn.PB_STYLE_NOBG)
        # self.recBtn = wx.BitmapButton(self, -1, self.ICON_RECORD[0], size=(24, 24), style=wx.NO_BORDER)
        # self.configBtn = wx.BitmapButton(self, -1, self.ICON_CONFIG[0], size=(24, 24), style=wx.NO_BORDER)

        for btn, icons in ((self.recBtn, self.ICON_RECORD), (self.configBtn, self.ICON_CONFIG)):
            btn.SetBackgroundColour(bg)
            btn.SetBitmapFocus(icons[1])
            btn.SetBitmapSelected(icons[2])
            btn.SetBitmapDisabled(icons[3])

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(sizer)
        sizer.Add(self.recBtn, 0, wx.EXPAND)
        sizer.Add(self.configBtn, 0, wx.EXPAND)
        sizer.Fit(self)


    @classmethod
    def loadIcons(cls):
        if cls.ICON_CONFIG:
            return

        cls.ICON_CONFIG = [img.GetBitmap() for img in button_config]
        cls.ICON_RECORD = [img.GetBitmap() for img in button_record]
        cls.ICON_STOP = [img.GetBitmap() for img in button_stop]
