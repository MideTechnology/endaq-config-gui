"""
Small utility functions, 'constants', and such, used by multiple files.

:author: dstokes

:todo: Update `isNewer()` and `parseVersion()` to better suit the new
    version numbering system (`W.X.Y[(a|b|rc)Z]`).
:todo: Some of these aren't used; identify and refactor/remove at some point.
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
# Numeric and math-related helper functions
# ===============================================================================

def expandRange(r, *vals):
    """ Given a two element list containing a minimum and maximum value,
        expand it if the given value is outside that range.
    """
    r[0] = min(r[0], *vals)
    r[1] = max(r[1], *vals)


def mapRange(x, in_min, in_max, out_min, out_max):
    """ Given a value `x` between `in_min` and `in_max`, get the equivalent
        value relative to `out_min` and `out_max`.
    """
    return ((x - in_min + 0.0) * (out_max - out_min) /
            (in_max - in_min) + out_min)


def nextPow2(x):
    """ Round up to the next greater than or equal to power-of-two.
    """
    x = int(x)
    if x & (x - 1) == 0:
        # already a power of 2
        return x

    # Kind of a hack, but it's fast (the 'right' way uses slow bit shifting).
    return 2 ** (len(bin(x)) - 2)


def roundUp(x, increment):
    """ Round up to the next increment.
    """
    n = x // increment
    if x % increment != 0:
        n += 1
    return n * increment


def constrain(x, minVal, maxVal):
    """ Return a value within a given range. Values outside the given range
        will produce the specified minimum or maximum, respectively.
        Functionally equivalent to ``min(maxVal, max(x, minVal))`` but much
        faster.
    """
    if x < minVal:
        return minVal
    elif x > maxVal:
        return maxVal
    else:
        return x


def lesser(x, y):
    """ Return the lesser of two values. Faster than ``min()`` for only two
        values. Note: does not work like ``min()`` with sequences!
    """
    return x if x < y else y


def greater(x, y):
    """ Return the greater of two values. Faster than ``max()`` for only two
        values. Note: does not work like ``max()`` with sequences!
    """
    return x if x > y else y


# ===============================================================================
# Formatting and parsing helpers
# ===============================================================================

def multiReplace(s, *replacements):
    """ Perform multiple substring replacements, provided as one or more
        two-item tuples containing pairs of old and new substrings.
    """
    for old, new in replacements:
        s = s.replace(old, new)
    return s


def wordJoin(words, conj="and", oxford=True):
    """ Function to do an English joining of list items.

        :param words: A list (or other iterable) of items. Items will be cast
            to Unicode.
        :param conj: The conjunction to use, e.g. ``"and"`` or ``"or"``.
        :param oxford: If `True`, insert a comma after the penultimate word,
            if ``words`` contains three or more items.
    """
    numWords = len(words)
    if numWords == 0:
        return ""
    elif numWords == 1:
        return words[0]
    elif numWords == 2:
        return (" %s " % conj).join(words)
    else:
        if oxford:
            return "%s, %s %s" % (', '.join(words[:-1]), conj, words[-1])
        else:
            return "%s %s %s" % (', '.join(words[:-1]), conj, words[-1])


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
