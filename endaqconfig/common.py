"""
Small utility functions, 'constants', and such, used by multiple files.

:author: dstokes
"""

import calendar
from datetime import datetime
import sys
import time

import wx

try:
    from ctypes import windll

    DOUBLE_CLICK_DEBOUNCE_TIME = windll.user32.GetDoubleClickTime()
except (ImportError, AttributeError):
    DOUBLE_CLICK_DEBOUNCE_TIME = 300


# ===============================================================================
#
# ===============================================================================

def isCompiled():
    """ Is this a compiled (i.e. with PyInstaller) application?
    """
    return getattr(sys, 'frozen', False)


#===============================================================================
# Time utility functions, etc.
#===============================================================================

def datetime2int(val, tzOffset=0):
    """ Convert a date/time object (either a standard Python datetime.datetime
        or wx.DateTime) into the UTC epoch time (i.e. UNIX time stamp).
    """
    if isinstance(val, wx.DateTime):
        return val.GetTicks() + tzOffset
    return int(calendar.timegm(val.utctimetuple()) + tzOffset)


def time2int(val, tzOffset=0):
    """ Parse a time string (as returned from `TimeCtrl.GetValue()`) into
        seconds since midnight.
    """
    t = datetime.strptime(str(val), '%H:%M:%S')
    return int((t.hour * 60 * 60) + (t.minute * 60) + t.second + tzOffset)


def makeWxDateTime(val):
    """ Create a `wx.DateTime` instance from a standard `datetime`, time tuple
        (or a similar 'normal' tuple), epoch timestamp, or another
        `wx.DateTime` object.
    """
    if isinstance(val, datetime):
        val = datetime2int(val)
    if isinstance(val, (int, float)):
        val = time.gmtime(val)
    elif isinstance(val, wx.DateTime):
        # XXX: Not sure this is correct for wxPython4
        # return wx.DateTimeFromDateTime(val)
        return val
    # Assume a struct_time or other sequence:
    return wx.DateTime.FromDMY(val[2], val[1]-1, val[0], val[3], val[4], val[5])


def getUtcOffset(seconds=False):
    """ Get the local offset from UTC time, in hours or seconds (float).
    """
    gt = time.gmtime()
    lt = time.localtime()
    val = (time.mktime(lt) - time.mktime(gt))
    if lt.tm_isdst == 1:
        val += 3600

    if not seconds:
        val /= 60.0 * 60.0

    return val
