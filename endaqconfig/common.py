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
    # noinspection PyUnresolvedReferences
    DOUBLE_CLICK_DEBOUNCE_TIME = windll.user32.GetDoubleClickTime()
except (ImportError, AttributeError):
    DOUBLE_CLICK_DEBOUNCE_TIME = 300


from endaq.device import Recorder, DeviceStatusCode


# ===============================================================================
#
# ===============================================================================

def isCompiled() -> bool:
    """ Is this a compiled (i.e. with PyInstaller) application?
    """
    return getattr(sys, 'frozen', False)


#===============================================================================
# Time utility functions, etc.
#===============================================================================

def datetime2int(val: datetime | wx.DateTime,
                 tzOffset: int = 0):
    """ Convert a date/time object (either a standard Python datetime.datetime
        or wx.DateTime) into the UTC epoch time (i.e. UNIX time stamp).
    """
    if isinstance(val, wx.DateTime):
        return val.GetTicks() + tzOffset
    return int(calendar.timegm(val.utctimetuple()) + tzOffset)


def time2int(val: str, tzOffset: int = 0) -> int:
    """ Parse a time string (as returned from `TimeCtrl.GetValue()`) into
        seconds since midnight.
    """
    t = datetime.strptime(str(val), '%H:%M:%S')
    return int((t.hour * 60 * 60) + (t.minute * 60) + t.second + tzOffset)


def makeWxDateTime(val: datetime | wx.DateTime | int | float) -> wx.DateTime:
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


def getUtcOffset(seconds=False) -> int | float:
    """ Get the local offset from UTC time, in hours or seconds (float).

        :param seconds: If `True`, return the offset in whole seconds. If
            `False`, return the offset in fractional hours.
    """
    gt = time.gmtime()
    lt = time.localtime()
    val = (time.mktime(lt) - time.mktime(gt))
    if lt.tm_isdst == 1:
        val += 3600

    if not seconds:
        val /= 60.0 * 60.0

    return val


#===============================================================================
#
#===============================================================================

def deviceString(device: Recorder):
    """ Little utility function to generate a nice string for a recorder.
    """
    # TODO: Move this to `Recorder.__str__()`?
    if device.name:
        return f'{device.productName} "{device.name}" ({device.serial})'
    else:
        return f"{device.productName} ({device.serial})"


#===============================================================================
#
#===============================================================================

def getClipboardText() -> str:
    """ Retrieve text from the clipboard.
    """
    if not wx.TheClipboard.IsOpened():
        wx.TheClipboard.Open()

    obj = wx.TextDataObject()
    if wx.TheClipboard.GetData(obj):
        return obj.GetText()

    return ""


#===============================================================================
# Device status checks
#===============================================================================

def isOnline(device: Recorder) -> bool:
    """ Is the device in an 'online' state? Note that local USB devices are
        inherently online.
    """
    if device.isVirtual:
        return False
    elif not device.isRemote:
        return True

    # TODO: Also exclude timed out devices?
    status = device.command.status[1]
    if status is not None and 300 <= status < 500:
        # Codes 400-499 are 'offline' variants of positive codes 0-99
        return False
    return status not in (DeviceStatusCode.ERR_DISCONNECTED,
                          DeviceStatusCode.OFFLINE,
                          DeviceStatusCode.SHUTDOWN,
                          DeviceStatusCode.RESET_PENDING,
                          DeviceStatusCode.START_PENDING,
                          DeviceStatusCode.STOP_PENDING,
                          DeviceStatusCode.UPLOADING,
                          None)


def isSleeping(device: Recorder) -> bool:
    """ Is the device in a 'sleeping' state?
    """
    status = device.command.status[1]
    if status is not None and 200 <= status < 400:
        # Codes 300-399 are 'periodic' variants of positive codes 0-99
        return True
    return status in (DeviceStatusCode.SLEEPING,
                      DeviceStatusCode.WAKING)


def isGateway(device: Recorder) -> bool:
    """ Is the device a HDS Gateway box?
    """
    # Gateway-ness determined by bits in the "recorder's" `RecorderTypeUID`.
    devtype = device.getInfo('RecorderTypeUID', 0)
    return bool(devtype & 0x20000000)  # bit and 29 (gateway)
