"""
Created on Sep 10, 2015

:author: dstokes
"""
from datetime import datetime

import wx
import wx.adv
import wx.lib.masked as wx_mc

# import images as images

#===============================================================================
# Custom widgets
#===============================================================================


class DateTimeCtrl(wx.Panel):
    """ A dual date/time combination widget. Not sure why wxPython doesn't
        have one.
    """

    def __init__(self, *args, **kwargs):
        """ Constructor. Takes standard `wx.lib.masked.TimeCtrl` arguments,
            plus:

            :keyword dateStyle: See `wx.adv.DatePickerCtrl`
            :keyword fmt24hr: See `wx.lib.masked.TimeCtrl`.
        """
        dateStyle = kwargs.pop('dateStyle', wx.adv.DP_DROPDOWN)
        fmt24hr = kwargs.pop('fmt24hr', True)
        super(DateTimeCtrl, self).__init__(*args, **kwargs)

        self.dateCtrl = wx.adv.DatePickerCtrl(self, -1, style=dateStyle)
        self.timeCtrl = wx_mc.TimeCtrl(self, 1, fmt24hr=fmt24hr)
        timeSpin = wx.SpinButton(self, 1, style=wx.SP_VERTICAL)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.dateCtrl, 1, wx.EXPAND)
        sizer.Add(self.timeCtrl, 1, wx.EXPAND)
        sizer.Add(timeSpin, -1, wx.EXPAND)
        self.SetSizer(sizer)
        self.timeCtrl.BindSpinButton(timeSpin)


    def SetValue(self, value):
        """ Set the value from a `wx.DateTime` object.

            :type value: `wx.DateTime`
        """
        self.dateCtrl.SetValue(value)
        self.timeCtrl.ChangeValue(value)


    def GetValue(self):
        """ Get the value as a `wx.DateTime` object.

            :rtype: `wx.DateTime`
        """
        t = self.timeCtrl.GetValue(as_wxDateTime=True)
        dt = self.dateCtrl.GetValue()
        dt.SetHour(t.GetHour())
        dt.SetMinute(t.GetMinute())
        dt.SetSecond(t.GetSecond())
        return dt


# XXX: REMOVE THIS ONCE `wx.DateTime.FromTimeT()` IS FIXED!
#  Issue: https://github.com/wxWidgets/Phoenix/issues/1910
#  Issue closed, but fixed version not yet released as of 2021-04-12.
def wx_DateTime_FromTimeT(timet):
    """ Construct a DateTime from a C time_t value, the number of seconds since the epoch.
        THIS IS A WORKAROUND HACK, TO BE REMOVED LATER!

        :param timet: Epoch timestamp (int or float)
        :rtype: `wx.DateTime`
    """
    dt = wx.DateTime.Now()
    dt.ParseISOCombined(datetime.fromtimestamp(timet).isoformat())
    return dt


#===============================================================================
# Field validators
#===============================================================================

class TimeValidator(wx.Validator):
    """
    """
    validCharacters = "-.0123456789"

    def __init__(self):
        super(TimeValidator, self).__init__()
        self.Bind(wx.EVT_CHAR, self.OnChar)

    def Clone(self):
        return TimeValidator()

    def Validate(self, win):
        val = self.GetWindow().GetValue()
        return all((c in self.validCharacters for c in val))

    def OnChar(self, evt):
        key = evt.GetKeyCode()

        if key < wx.WXK_SPACE or key == wx.WXK_DELETE or key > 255:
            evt.Skip()
            return

        if chr(key) in self.validCharacters:
            evt.Skip()
            return

#         if not wx.Validator_IsSilent():
#             wx.Bell()
        return
