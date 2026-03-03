"""
Created on Sep 10, 2015

:author: dstokes
"""

from datetime import datetime, timedelta
import logging
import re
import socket
from time import time
from typing import Any, Dict, Optional, Tuple

import wx
import wx.adv
import wx.lib.masked as wx_mc

from endaq.device.mqtt.discovery import findBrokers
from endaq.device.util import getMyIP

from .events import EvtBrokerUpdate
from .controls import getStatusDisplay

logger = logging.getLogger(__name__)


#===============================================================================
#
#===============================================================================

def getClipboardText():
    """ Retrieve text from the clipboard.
    """
    if not wx.TheClipboard.IsOpened():
        wx.TheClipboard.Open()

    obj = wx.TextDataObject()
    if wx.TheClipboard.GetData(obj):
        return obj.GetText()

    return ""


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


    def GetValue(self) -> wx.DateTime:
        """ Get the value as a `wx.DateTime` object.

            :rtype: `wx.DateTime`
        """
        t: wx.DateTime = self.timeCtrl.GetValue(as_wxDateTime=True)
        dt = self.dateCtrl.GetValue()
        dt.SetHour(t.GetHour())
        dt.SetMinute(t.GetMinute())
        dt.SetSecond(t.GetSecond())
        return dt


def wx_DateTime_FromTimeT(timet: int | float) -> wx.DateTime:
    """ Construct a DateTime from a C time_t value, the number of seconds
        since the epoch.

        This was originally a workaround for a wxPython bug; it's
        reportedly fixed, but this hack isn't too bad.

        :param timet: Epoch timestamp (int or float)
    """
    dt = wx.DateTime.Now()
    dt.ParseISOCombined(datetime.fromtimestamp(timet).isoformat())
    return dt


#===============================================================================
# Field validators
#===============================================================================

class FieldValidationError(Exception):
    """ Raised when a validator fails. """


class TextValidator(wx.Validator):
    """ Generic Validator for TextField and ASCIIField text widgets.
    """

    VALID_KEYS = (wx.WXK_LEFT, wx.WXK_UP, wx.WXK_RIGHT, wx.WXK_DOWN,
                  wx.WXK_HOME, wx.WXK_END, wx.WXK_PAGEUP, wx.WXK_PAGEDOWN,
                  wx.WXK_INSERT, wx.WXK_DELETE)


    def __init__(self, validChar=None, validator=None, minLen=0, maxLen=float('inf')):
        """ Instantiate a text field validator. It does basic validation of
            min/max length, and uses supplied functions to validate contents.

            :param validChar: A function that validates each character as entered.
            :param validator: A function that validates the entire string.
            :param minLen: Minimum length of the string.
            :param maxLen: Maximum length of the string.
        """
        self.minLen = minLen or 0
        self.maxLen = maxLen or float('inf')
        self.isValidChar = validChar or (lambda x: True)
        self.isValidString = validator or (lambda x: True)

        self.tooltip = None  # Field's original tooltip, gets message appended if validation fails
        self.colorValid = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        self.colorInvalid = wx.Colour("pink")

        wx.Validator.__init__(self)
        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.Bind(wx.EVT_TEXT_PASTE, self.OnPaste)


    def GetWindow(self) -> wx.TextCtrl:
        # This just exists to set the return type hint for the sake of the linter.
        return super().GetWindow()


    def Clone(self):
        """ Required in wx.PyValidator subclasses. """
        return TextValidator(self.isValidChar, self.isValidString,
                             self.minLen, self.maxLen)


    def TransferToWindow(self):
        """ Required in wx.PyValidator subclasses. """
        return True


    def TransferFromWindow(self):
        """ Required in wx.PyValidator subclasses. """
        return True


    def Validate(self, win):
        """ Perform validation. Changes the field background color and adds a
            message to the tooltip if invalid.
        """
        if not win.IsEnabled():
            return True

        txt = win.GetValue()
        msg = ''

        # if self.minLen >= len(txt) > self.maxLen:
        if not self.minLen <= len(txt) <= self.maxLen:
            if self.maxLen == float('inf'):
                msg = f'⚠ Length must be at least {self.minLen} characters!'
            elif self.minLen == 0:
                msg = f'⚠ Length must be shorter than {self.minLen} characters!'
            else:
                msg = f'⚠ Length must be between {self.minLen} and {self.maxLen} characters!'
            valid = False
        else:
            try:
                valid = self.isValidString(txt)
            except FieldValidationError as e:
                valid = False
                msg = f'⚠ {e}'

        tooltip = (win.GetToolTipText() or '').partition('⚠')[0].strip()
        win.SetToolTip(f'{tooltip}\n\n{msg}'.strip())
        win.SetBackgroundColour(self.colorValid if valid else self.colorInvalid)
        win.Refresh()
        return valid


    def OnChar(self, evt):
        """ Validate a character that has been typed.
        """
        key = evt.GetKeyCode()

        if key < wx.WXK_SPACE or key in self.VALID_KEYS:
            evt.Skip()
            return

        val = self.GetWindow().GetValue()
        if self.isValidChar(chr(key)) and len(val) < self.maxLen:
            evt.Skip()
            return
        elif not wx.Validator.IsSilent():
            wx.Bell()

        return


    def OnPaste(self, evt):
        """ Validate text pasted into the field.
        """
        txt = getClipboardText()
        current = self.GetWindow().GetValue()
        new = current + txt
        if self.isValidString(new):
            evt.Skip()
        elif not wx.Validator.IsSilent():
            wx.Bell()


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
        self.device = None

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

        self.lineHeight = self.GetTextExtent('Wg')[1]

        self.timer = wx.Timer(self)
        self.updateTimer = wx.Timer(self)

        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_TIMER, self.OnShowTimerTick, self.timer)
        self.Bind(wx.EVT_TIMER, self.OnUpdateTimerTick, self.updateTimer)
        self.Enable(False)


    def setText(self, text: Optional[str]):
        """ Update the hovering display.
        """
        if not text:
            self.text = ''
            self.timer.Stop()
            return

        self.text = text.strip()


    def makeText(self) -> str:
        """ Generate the complete text for the tooltip.
        """
        if self.device:
            if self.device.name:
                text = f'{self.device.productName} "{self.device.name}" ({self.device.serial})\n'
            else:
                text = f"{self.device.productName} ({self.device.serial})\n"
            if self.device.command.status[0]:
                stime, scode, smsg = self.device.command.status
                stext = getStatusDisplay(scode)[-1]
                stime = self.device._lastContact if self.device.isRemote else stime
                if smsg:
                    text += f'Status: {stext}: {smsg} (updated {prettyTimeDiff(stime)} ago)\n'
                else:
                    text += f'Status: {stext} (updated {prettyTimeDiff(stime)} ago)\n'

                lockId = self.device.command.lockId[1]
                if lockId:
                    if lockId == self.device.command.hostId:
                        text += 'You have exlusive control of this device.\n'
                    elif any(lockId):
                        text += 'This device is currently in use by another user/process.\n'

        else:
            logger.debug(f'DeviceToolTip.device is {self.device!r} (should not happen)')
            text = ''

        return text + self.text


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


    def Show(self, show: bool = True) -> bool:
        """ Shows or hides the window.
        """
        if not show:
            self.updateTimer.Stop()
            return super().Show(False)

        text = self.makeText()
        if not text:
            return False

        w = h = 0
        for line in text.split('\n'):
            lw, lh = self.GetTextExtent(line)
            w = max(w, lw)
            h += max(self.lineHeight, lh)
        self.SetSize((w + 10, h + 10))
        self.textWidget.SetLabel(text)

        self.updateTimer.Start(1000)
        return super().Show()


    def Hide(self) -> bool:
        return self.Show(False)


    def OnUpdateTimerTick(self, _evt):
        """ Update the tooltip content when the timer expires.
        """
        # logger.debug('DeviceToolTip.OnUpdateTimerTick')

        if not self.IsShown():
            # Unlikely, but not impossible (e.g., an error in `Show()`)
            self.updateTimer.Stop()
            return

        text = self.makeText()
        if text:
            self.textWidget.SetLabel(text)
        else:
            # Also unlikely, but not impossible
            self.Show(False)


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
    connect will be tested (optional). ``localhost`` is a special case,
    and gets converted to the computer's actual IP.

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

# class _BrokerField(wx.Panel):
#     """
#     A widget for selecting an MQTT broker, either from advertising or
#     a manually-entered IP address.
#
#     """
#
#     # Background/foreground color of selection field if the broker
#     # name/address is invalid. `None` means that color doesn't change.
#     BAD_COLOR = (wx.Colour(255, 200, 200), None)
#
#
#     def __init__(self, *args, **kwargs):
#         """
#         A widget for selecting an MQTT broker, either from advertising or
#         a manually-entered IP address. Takes standard `wx.Panel` arguments,
#         plus:
#
#         :keyword selectedName: The default broker name/address
#         :keyword validate: If `True`, check that manually-entered IP addresses
#             are correctly formed.
#         :keyword verify: If `True`, test connecting the selected broker.
#         :keyword verifyTimeout: The time to wait before declaring verification failed.
#         :keyword scantime: The minimum time (in seconds) to scan for brokers. If
#             any brokers are discovered in this time, they will be returned.
#         :keyword timeout: The maximum time (in seconds) to scan for brokers, if
#             none were found in `scantime`.
#         :keyword callback: A function to call repeatedly while scanning. If the
#             callback returns `True`, the wait for a response will be cancelled.
#             The callback function should require no arguments.
#         """
#         self.selectedName = kwargs.pop('default', None)
#         self.validate = kwargs.pop('validate', True)
#         self.verify = kwargs.pop('verify', False)
#         self.verifyTimeout = kwargs.pop('verifyTimeout', 0.25)
#
#         self.scanKwargs = {}
#         for k in ('scanTime', 'timeout', 'callback'):
#             if k in kwargs:
#                 self.scanKwargs[k] = kwargs.pop(k)
#
#         super().__init__(*args, **kwargs)
#
#         sizer = wx.BoxSizer(wx.HORIZONTAL)
#         self.brokerText = wx.StaticText(self, -1, "Broker:")
#         sizer.Add(self.brokerText, 0, wx.ALL, 4)
#         self.brokerList = wx.ComboBox(self, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
#         sizer.Add(self.brokerList, 4, wx.EXPAND)
#         self.brokerScanBtn = wx.Button(self, -1, "Rescan")
#         sizer.Add(self.brokerScanBtn, 1, wx.EXPAND)
#         self.SetSizer(sizer)
#
#         self.brokers = {}  # Broker info dicts keyed by broker name
#         self.names = []  # Broker names (sorted keys of `brokers`)
#         self.tooltip = ''
#
#         self.defaultColors = (self.brokerList.GetBackgroundColour(),
#                               self.brokerList.GetForegroundColour())
#
#         self.updateList()
#         if self.selectedName and self.selectedName not in self.brokers:
#             self.brokerList.SetValue(self.selectedName)
#             self.validateSelection()
#         else:
#             self.selectedName = self.GetString()
#
#         self.Bind(wx.EVT_BUTTON, self.OnBrokerScan, self.brokerScanBtn)
#         self.Bind(wx.EVT_COMBOBOX, self.OnBrokerSelection, self.brokerList)
#         self.Bind(wx.EVT_TEXT_ENTER, self.OnBrokerListEntered, self.brokerList)
#
#
#     def updateList(self):
#         """ Scan for mDNS advertised brokers and update the display.
#         """
#         try:
#             self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
#             self.brokerList.Enable(False)
#             self.brokerScanBtn.Enable(False)
#
#             # self.selectedName = self.GetString()
#
#             self.brokers = {b['name']: b for b in findBrokers(None, **self.scanKwargs)}
#             self.names = sorted(self.brokers)
#
#             if self.names and not self.selectedName:
#                 self.selectedName = self.names[0]
#
#             self.brokerList.SetItems(self.names)
#             if self.selectedName in self.brokers:
#                 self.brokerList.SetSelection(self.names.index(self.selectedName))
#                 self._setSelectedToolTip()
#             else:
#                 self.brokerList.SetValue(self.selectedName)
#                 self.validateSelection()
#
#         finally:
#             self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
#             self.brokerList.Enable(True)
#             self.brokerScanBtn.Enable(True)
#
#
#     def _setListColor(self, color):
#         """ Convenience method to set the list back/fore colors.
#         """
#         bg, fg = color
#         self.brokerList.SetBackgroundColour(bg or self.defaultColors[0])
#         self.brokerList.SetForegroundColour(fg or self.defaultColors[1])
#
#
#     def _setSelectedToolTip(self):
#         """ Update the list tooktip for the currently selected broker name.
#         """
#         selected = self.GetString()
#         if not selected:
#             self.brokerList.SetToolTip('')
#             return
#
#         info = self.brokers.get(selected)
#         if not info:
#             logger.error(f'No broker info for {info!r} (should not happen!)')
#             self.brokerList.SetToolTip('')
#             return
#
#         self.brokerList.SetToolTip("{name}.{serviceType}\nIP {host[0]} port {port}".format(**info))
#
#
#     def validateSelection(self) -> bool:
#         """ Check that the currently selected (or typed) broker IP address
#             is valid and update the tooltip. Bad values are indicated by
#             the list background color.
#
#             :return: True if valid, False otherwise.
#         """
#         if not self.validate:
#             return True
#
#         txt = self.GetString()
#         try:
#             ip, port = parseIP(txt, check=False)
#         except ValueError:
#             self._setListColor(self.BAD_COLOR)
#             self.brokerList.SetToolTip('Invalid IP address')
#             return False
#
#         if self.verify:
#             try:
#                 self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
#                 self.brokerList.Enable(False)
#                 self.brokerScanBtn.Enable(False)
#                 parseIP(txt, check=False)
#             except ValueError:
#                 self._setListColor(self.BAD_COLOR)
#                 self.brokerList.SetToolTip('Could not connect to address')
#                 return False
#             finally:
#                 self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
#                 self.brokerList.Enable(True)
#                 self.brokerScanBtn.Enable(True)
#
#         if ip.lower() == 'localhost':
#             ip = getMyIP()
#
#         self.brokerList.SetToolTip(f'IP {ip} port {port}')
#         self._setListColor(self.defaultColors)
#         return True
#
#
#     def postSelectionEvent(self):
#         """ Post a broker selection event to the main window.
#         """
#         logger.debug('Posting broker change')
#
#         # TODO: Make sure this works when called through enDAQ Lab, etc.
#         dest = wx.GetActiveWindow()
#         wx.PostEvent(dest, EvtBrokerUpdate(broker=self.GetValue()))
#
#
#     def OnBrokerScan(self, _evt):
#         """ Handle the 'Rescan' button event.
#         """
#         logger.debug('OnBrokerScan')
#         self.selectedName = self.GetString()
#         self.updateList()
#
#
#     def OnBrokerSelection(self, _evt):
#         """ Handle broker selection.
#         """
#         txt = self.brokerList.GetValue()
#         current = self.GetString()
#         if self.selectedName != current:
#             self.postSelectionEvent()
#             self.selectedName = current
#             self._setSelectedToolTip()
#         else:
#             logger.debug('Same broker selected, not posting event')
#
#
#     def OnBrokerListEntered(self, _evt):
#         """ Handle 'enter' being pressed in the list text field.
#         """
#         name = self.GetString()
#         if not name:
#             self.brokerList.SetValue(self.selectedName)
#         else:
#             self.selectedName = name
#             if self.validateSelection():
#                 self.postSelectionEvent()
#
#
#     def GetValue(self) -> Dict[str, Any]:
#         """ Get the info dictionary for the selected broker.
#         """
#         selected = self.GetString()
#         if selected in self.brokers:
#             return self.brokers.get(selected)
#         else:
#             try:
#                 ip, port = parseIP(self.selectedName, check=False)
#                 if ip.lower() == 'localhost':
#                     ip = getMyIP()
#                 return {'name': selected,
#                         'serviceType': '_endaq._tcp.local.',
#                         'host': [ip],
#                         'port': port,
#                         'properties': {}}
#             except ValueError:
#                 return None
#
#
#     def GetString(self) -> str:
#         """ Get the currently selected broker name/IP.
#         """
#         return self.brokerList.GetValue().strip()
#
#
#     def IsValid(self) -> bool:
#         """ Is the currently-selected broker name/address valid?
#         """
#         broker = self.GetValue()
#         return bool(broker)


class BrokerField(wx.Panel):
    """
    A widget for selecting an MQTT broker, either from advertising or
    a manually-entered IP address.

    """

    # Background/foreground color of selection field if the broker
    # name/address is invalid. `None` means that color doesn't change.
    BAD_COLOR = (wx.Colour(255, 200, 200), None)

    ID_USER_BROKER = wx.NewIdRef()
    ID_ADD_BROKER = wx.NewIdRef()


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

        try:
            self.userIp = parseIP(self.selectedName, check=False)
        except ValueError:
            self.userIp = None

        self.scanKwargs = {}
        for k in ('scanTime', 'timeout', 'callback'):
            if k in kwargs:
                self.scanKwargs[k] = kwargs.pop(k)

        super().__init__(*args, **kwargs)

        # Supposedly, only Windows and GTK support text justification in buttons.
        # Only add left padding if text aligned left.
        self._justified = any(x in wx.PlatformInfo for x in ('__WXMSW__', '__WXGTK__'))

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.brokerText = wx.StaticText(self, -1, "Broker:")
        sizer.Add(self.brokerText, 0, wx.ALL, 4)
        self.brokerBtn = wx.Button(self, label='', style=wx.BU_LEFT)
        sizer.Add(self.brokerBtn, 4, wx.EXPAND)
        self.brokerScanBtn = wx.Button(self, -1, "Rescan")
        sizer.Add(self.brokerScanBtn, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.brokers: dict[str, dict] = {}  # Broker info dicts keyed by broker name
        self.names: list[str] = []  # Broker names (sorted keys of `brokers`)
        self.tooltip: str = ''

        self.brokersByItemID = {}
        self.itemIDsByBroker = {}

        self.defaultColors = (self.brokerBtn.GetBackgroundColour(),
                              self.brokerBtn.GetForegroundColour())

        self.updateList()

        self.Bind(wx.EVT_BUTTON, self.OnBrokerScan, self.brokerScanBtn)
        self.Bind(wx.EVT_BUTTON, self.OnBrokerClick, self.brokerBtn)
        self.Bind(wx.EVT_MENU, self.OnBrokerSelection)


    def setSelectedName(self, name):
        if self.names and not name:
            name = self.names[0]
        self.selectedName = name
        prefix = '   ' if self._justified else ''
        self.brokerBtn.SetLabel(f'{prefix}{self.selectedName}')
        self._setSelectedToolTip()


    def updateList(self):
        """ Scan for mDNS advertised brokers and update the display.
        """
        try:
            self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
            self.brokerBtn.Enable(False)
            self.brokerScanBtn.Enable(False)

            name = self.GetString()

            self.brokers = {b['name']: b for b in findBrokers(None, **self.scanKwargs)}
            self.names = sorted(self.brokers)

            self.setSelectedName(name)

        finally:
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            self.brokerBtn.Enable(True)
            self.brokerScanBtn.Enable(True)


    def _setSelectedToolTip(self):
        """ Update the list tooktip for the currently selected broker name.
        """
        selected = self.GetString()
        if not selected:
            self.brokerBtn.SetToolTip('')
            return

        info = self.brokers.get(selected)
        if not info:
            logger.error(f'No broker info for {info!r} (should not happen!)')
            self.brokerBtn.SetToolTip('')
            return

        self.brokerBtn.SetToolTip("{name}.{serviceType}\nIP {host[0]} port {port}".format(**info))


    def postSelectionEvent(self):
        """ Post a broker selection event to the main window.
        """
        logger.debug('Posting broker change')

        # TODO: Make sure this works when called through enDAQ Lab, etc.
        dest = wx.GetActiveWindow()
        wx.PostEvent(dest, EvtBrokerUpdate(broker=self.GetValue()))


    def OnBrokerScan(self, _evt):
        """ Handle the 'Rescan' button event.
        """
        logger.debug('OnBrokerScan')
        self.selectedName = self.GetString()
        self.updateList()


    def OnBrokerClick(self, _evt):
        """ Handle clicking of broker field. """
        menu = wx.Menu()
        self.itemIDsByBroker.clear()
        for broker in self.names:
            mid = self.itemIDsByBroker.get(broker, -1)
            item = menu.AppendRadioItem(mid, broker)
            item.Check(broker == self.selectedName)
            self.brokersByItemID[item.GetId()] = broker
            self.itemIDsByBroker[broker] = item.GetId()

        # menu.AppendSeparator()
        # menu.AppendRadioItem(self.ID_USER_BROKER, 'IP Address:')
        self.PopupMenu(menu)
        menu.Destroy()


    def OnBrokerSelection(self, evt):
        """ Handle broker selection.
        """
        mid = evt.GetId()
        if mid in self.brokersByItemID:
            txt = self.brokersByItemID[mid]
            if txt != self.selectedName:
                self.setSelectedName(txt)
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
        """ Get the currently selected broker name/IP.
        """
        return self.selectedName


    def IsValid(self) -> bool:
        """ Is the currently-selected broker name/address valid?
        """
        broker = self.GetValue()
        return bool(broker)


def prettyTimeDiff(t1: float, t2: Optional[float] = None, abstime=True) -> str:
    """ Return a pretty time difference between two timestamps.

        :param t1: First timestamp.
        :param t2: Second timestamp. Defaults to the current time.
        :param abstime: If `True` (default), show the absolute value time.return a string that represents the time difference.
    """
    if t2 is None:
        t2 = time()
    ts = int(abs(t2 - t1))
    sign = '-' if t2 < t1 and not abstime else ''
    if ts < 60:
        return f"{sign}0:{ts:02d}"
    return f"{sign}{str(timedelta(seconds=ts)).lstrip('0:')}"
