"""
Created on Sep 10, 2015

:author: dstokes
"""

from datetime import datetime
import logging
import re
import socket
from typing import Any, Dict, Optional, Tuple

import wx
import wx.adv
import wx.lib.masked as wx_mc

from endaq.device.mqtt.discovery import findBrokers
from endaq.device.util import getMyIP

from .events import EvtBrokerUpdate

logger = logging.getLogger(__name__)

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


# ===========================================================================
#
# ===========================================================================

class DeviceToolTip(wx.Frame):
    """ Tooltip display for device info. Must be explicitly shown (e.g.,
        after a mouse movement timer expires).

        If ULC tooltips get fixed, this may be redundant and can be removed if so.
    """

    TOOLTIP_TIME = 900
    MOUSE_OFFSET = wx.Point(0, 18)


    def __init__(self,
                 view: wx.Window):
        """ Tooltip display for device info.

            :param view: The parent view.
        """
        self.view = view
        self.text = None

        # Note: color not quite right.
        fgcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        bgcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)

        super().__init__(view, -1, style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.textWidget = wx.StaticText(self, -1, "", size=(64, 32))
        sizer.Add(self.textWidget, 1, wx.EXPAND | wx.ALL, 4)

        self.textWidget.SetForegroundColour(fgcolor)
        self.SetBackgroundColour(bgcolor)

        self.SetSizer(sizer)
        self.Fit()

        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_TIMER, self.OnShowTimerTick, self.timer)


    def setText(self, text: Optional[str]):
        """ Update the hovering display.
        """
        if not text:
            self.timer.Stop()
            return

        if text != self.text:
            self.text = text
            w = h = 0
            for line in text.split('\n'):
                lw, lh = self.GetTextExtent(line)
                w = max(w, lw)
                h += lh
            self.SetSize((w + 10, h + 10))
            self.textWidget.SetLabel(text)


    def OnMouseMove(self, evt):
        if self.IsShown():
            self.Hide()
        evt.Skip()


    def OnShowTimerTick(self, _evt):
        """ Handle the mouse motion timer expiring.
        """
        if not self.IsShown():
            self.SetPosition(wx.GetMousePosition() + self.MOUSE_OFFSET)
            self.Show()


# ===========================================================================
#
# ===========================================================================

def parseIP(val: str,
            defaultPort: int = 1883,
            check: bool = True,
            timeout: float = 0.25) -> Tuple[str, int]:
    """
    Validate and parse an IP address, optionally with a port number separated
    by a colon. If the structure of the address is valid, the ability to
    connect will be tested (optional).

    :param val: The IP address (e.g., ``192.168.0.1`` or ``192.168.0.1:1883``).
    :param defaultPort: The default port number to use (if not included in `val`).
    :param check: If `True`, verify a connection can be made to the address/port.
    :param timeout: Time to wait for the verification check.
    :return: The IP address and the port number.
    """
    try:
        if val.lower().startswith('localhost'):
            ip, _sep, port = val.partition(':')
            port = port or defaultPort
        else:
            ip, port = re.match(r"\b(\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?\b", val).groups()
            # This could probably be done in a more complex regular expression:
            if not all(0 <= int(part) <= 255 for part in ip.split('.')):
                raise ValueError

        port = int(port or defaultPort)
    except (AttributeError, ValueError, TypeError):
        raise ValueError(f'Invalid IP address: {val!r}') from None

    if check:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((ip, port))
        except (socket.timeout, socket.error, ConnectionRefusedError, OSError) as err:
            raise ValueError(f"Could not verify IP address '{ip}:{port}': {err}") from None

    return ip, port


# ===========================================================================
#
# ===========================================================================

class BrokerField(wx.Panel):
    """
    A widget for selecting an MQTT broker, either from advertising or
    a manually-entered IP address.

    @todo: implement manual entry of IP address!
    """

    # Warning symbol to append to bad names/IPs
    WARNING = ' \u26A0'

    BAD_COLOR = (wx.Colour(255, 200, 200), None)


    def __init__(self, *args, **kwargs):
        """
        A widget for selecting an MQTT broker, either from advertising or
        a manually-entered IP address. Takes standard `wx.Panel` arguments,
        plus:

        :keyword selectedName: The default broker name/address
        :keyword validate: If `True`, check that manually-entered IP addresses
            are correctly formed.
        :keyword verify: If `True`, test connecting the selected broker.
        :keyword verifyTimeout: The time to wait before declaring verification failed.
        :keyword scantime: The minimum time (in seconds) to scan for brokers. If
            any brokers are discovered in this time, they will be returned.
        :keyword timeout: The maximum time (in seconds) to scan for brokers, if
            none were found in `scantime`.
        :keyword callback: A function to call repeatedly while scanning. If the
            callback returns `True`, the wait for a response will be cancelled.
            The callback function should require no arguments.
        """
        self.selectedName = kwargs.pop('default', None)
        self.validate = kwargs.pop('validate', True)
        self.verify = kwargs.pop('verify', False)
        self.verifyTimeout = kwargs.pop('verifyTimeout', 0.25)

        self.scanKwargs = {}
        for k in ('scanTime', 'timeout', 'callback'):
            if k in kwargs:
                self.scanKwargs[k] = kwargs.pop(k)

        super().__init__(*args, **kwargs)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.brokerText = wx.StaticText(self, -1, "Broker:")
        sizer.Add(self.brokerText, 0, wx.ALL, 4)
        self.list = wx.ComboBox(self, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
        sizer.Add(self.list, 4, wx.EXPAND)
        self.brokerScanBtn = wx.Button(self, -1, "Rescan")
        sizer.Add(self.brokerScanBtn, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.brokers = {}  # Broker info dicts keyed by broker name
        self.names = []  # Broker names (sorted keys of `brokers`)
        self.tooltip = ''

        self.defaultColors = (self.list.GetBackgroundColour(),
                              self.list.GetForegroundColour())

        self.updateList()
        if self.selectedName and self.selectedName not in self.brokers:
            self.list.SetValue(self.selectedName)
            self.validateSelection()
        else:
            self.selectedName = self.GetString()

        self.Bind(wx.EVT_BUTTON, self.OnBrokerScan, self.brokerScanBtn)
        self.Bind(wx.EVT_COMBOBOX, self.OnBrokerSelection, self.list)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnBrokerListEntered, self.list)


    def updateList(self):
        """ Scan for mDNS advertised brokers and update the display.
        """
        try:
            self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
            self.list.Enable(False)
            self.brokerScanBtn.Enable(False)

            self.selectedName = self.GetString()

            self.brokers = {b['name']: b for b in findBrokers(**self.scanKwargs)}
            self.names = sorted(self.brokers)

            if not self.selectedName:
                self.selectedName = self.names[0]

            self.list.SetItems(self.names)
            if self.selectedName in self.names:
                self.list.SetSelection(self.names.index(self.selectedName))
                self._setSelectedToolTip()
            else:
                self.list.SetValue(self.selectedName)
                self.validateSelection()

        finally:
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            self.list.Enable(True)
            self.brokerScanBtn.Enable(True)


    def _setListColor(self, color):
        bg, fg = color
        self.list.SetBackgroundColour(bg or self.defaultColors[0])
        self.list.SetForegroundColour(fg or self.defaultColors[1])


    def _setSelectedToolTip(self):
        selected = self.GetString()
        if not selected:
            self.list.SetToolTip('')
            return

        info = self.brokers.get(selected)
        if not info:
            logger.error(f'No broker info for {info!r} (should not happen!)')
            self.list.SetToolTip('')
            return

        self.list.SetToolTip("{name}.{serviceType}\nIP {host[0]} port {port}".format(**info))


    def validateSelection(self):
        if not self.validate:
            return True

        txt = self.GetString()
        try:
            ip, port = parseIP(txt, check=False)
        except ValueError:
            self._setListColor(self.BAD_COLOR)
            self.list.SetToolTip('Invalid IP address')
            return False

        if self.verify:
            try:
                self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
                self.list.Enable(False)
                self.brokerScanBtn.Enable(False)
                parseIP(txt, check=False)
            except ValueError:
                self._setListColor(self.BAD_COLOR)
                self.list.SetToolTip('Could not connect to address')
                return False
            finally:
                self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
                self.list.Enable(True)
                self.brokerScanBtn.Enable(True)

        if ip.lower() == 'localhost':
            ip = getMyIP()

        self.list.SetToolTip(f'IP {ip} port {port}')
        self._setListColor(self.defaultColors)
        return True


    def postSelectionEvent(self):
        logger.debug('Posting broker change')
        wx.PostEvent(wx.GetActiveWindow(),
                     EvtBrokerUpdate(broker=self.GetValue()))


    def OnBrokerScan(self, _evt):
        """ Handle the 'Rescan' button event.
        """
        logger.debug('OnBrokerScan')
        self.selectedName = self.GetString()
        self.updateList()


    def OnBrokerSelection(self, _evt):
        """ Handle broker selection.
        """
        txt = self.list.GetValue()
        current = self.GetString()
        if self.selectedName != current:
            self.postSelectionEvent()
            self.selectedName = current
            self._setSelectedToolTip()
        else:
            logger.debug('Same broker selected, not posting event')


    def OnBrokerListEntered(self, _evt):
        """ Handle 'enter' being pressed in the list text field.
        """
        name = self.GetString()
        if not name:
            self.list.SetValue(self.selectedName)
        else:
            self.selectedName = name
            if self.validateSelection():
                self.postSelectionEvent()


    def GetValue(self) -> Dict[str, Any]:
        """ Get the info dictionary for the selected broker.
        """
        selected = self.GetString()
        if selected in self.brokers:
            return self.brokers.get(selected)
        else:
            try:
                ip, port = parseIP(self.selectedName, check=False)
                if ip.lower() == 'localhost':
                    ip = getMyIP()
                return {'name': selected,
                        'serviceType': '_endaq._tcp.local.',
                        'host': [ip],
                        'port': port,
                        'properties': {}}
            except ValueError:
                return None


    def GetString(self) -> str:
        return self.list.GetValue().replace(self.WARNING, '').strip()


    def IsValid(self) -> bool:
        """ Is the currently-selected broker name/address valid?
        """
        txt = self.list.GetValue()
        return txt and self.WARNING not in txt
