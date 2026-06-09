"""
Created on Sep 10, 2015

:author: dstokes
"""

from datetime import datetime, timedelta
import logging
import os.path
import re
import socket
from time import time
from typing import Any, Dict, Optional, Tuple

import wx
import wx.adv
import wx.lib.masked as wx_mc
import wx.lib.sized_controls as sc

from endaq.device.mqtt.discovery import findBrokers

from .events import EvtBrokerUpdate
from .controls import getStatusDisplay
from .icons import pw_show, pw_hide

from ..validators import TextValidator, FieldValidationError

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
        self.timeCtrl = wx_mc.TimeCtrl(self, -1, fmt24hr=fmt24hr)
        timeSpin = wx.SpinButton(self, -1, style=wx.SP_VERTICAL)

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


# ===========================================================================
#
# ===========================================================================

FONTFILE = os.path.join(os.path.dirname(__file__), 'password-dots.ttf')
FONTNAME = 'Password Dots'


class PasswordTextCtrl(wx.Panel):
    """
    Text field for passwords, with a show/hide clear text toggle button.

    Note that this is not a complete drop-in replacement for `wx.TextCtrl`;
    some `wx.TextCtrl` methods must be explicitly called on the internal
    `text_ctrl`. Event binding might also be weird.

    Uses the "Password Dots" font:

        The FontStruction “Password Dots”
        (https://fontstruct.com/fontstructions/show/1106896) by “JimProuty” is
        licensed under a Creative Commons Attribution license
        (https://creativecommons.org/licenses/by/3.0/).
        [ancestry]

    TODO: include font info in any documentation before release!
    """

    _STYLE = wx.TE_PROCESS_ENTER | wx.TE_RICH2


    def __init__(self,
                 parent: wx.Window,
                 id: int = wx.ID_ANY,
                 value: str = "",
                 style: int = _STYLE,
                 parent_style: int = wx.BORDER_NONE | wx.TRANSPARENT_WINDOW,
                 **kwargs):
        """ Text field for passwords, with a show/hide clear text toggle button.
            Takes standard `wx.TextCtrl` arguments, plus:

            :param parent_style: The style of the outer container. The standard
                `style` argument is applied to the inner text field.

        """
        self.text_kwargs = {}
        if validator := kwargs.pop('validator', None):
            self.text_kwargs['validator'] = validator

        super().__init__(parent, id, style=parent_style, **kwargs)

        self.textstyle = style
        self.text_ctrl = wx.TextCtrl(self,
                                     size=(self.GetSize().width - 40, -1),
                                     style=style,
                                     **self.text_kwargs)

        self.bmp_hidden = pw_show.GetBitmap()
        self.bmp_visible = pw_hide.GetBitmap()

        dis = pw_show.GetImage().AdjustChannels(1.0, 1.0, 1.0, 0.33)
        self.bmp_disabled = wx.Bitmap(dis, depth=32)

        self.staticbmp = wx.StaticBitmap(self, -1, self.bmp_hidden, pos=(5, 6))
        self.staticbmp.SetToolTip('Show Password')

        wx.Font.AddPrivateFont(FONTFILE)
        self.fontVisible = self.text_ctrl.GetFont()
        self.fontHidden = wx.Font(self.fontVisible)
        self.fontHidden.SetFaceName(FONTNAME)

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 0)
        self.sizer.Add(self.staticbmp, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)

        outersizer = wx.BoxSizer(wx.VERTICAL)
        outersizer.Add(self.sizer, 0, wx.ALL | wx.EXPAND, 0)
        self.SetSizer(outersizer)

        self.text_ctrl.SetMinSize((-1, self.text_ctrl.GetSize().height))

        self.hidden = True
        self.text_ctrl.SetFont(self.fontHidden)
        self.text_ctrl.SetValue(value)

        self.staticbmp.Bind(wx.EVT_LEFT_UP, self.OnShowPassword)


    def Enable(self, enable=True):
        """ Enable or disable the window for user input. """
        # NOTE: This doesn't get called if parent enabled/disabled!
        if not enable:
            self.showPassword(False)
            bmp = self.bmp_disabled
        else:
            bmp = self.bmp_hidden
        self.staticbmp.SetBitmap(bmp)

        return super().Enable(enable=enable)


    def Disable(self):
        """ Disables the window. """
        self.Enable(False)


    def Bind(self, *args, **kwargs):
        return self.text_ctrl.Bind(*args, **kwargs)


    def Unbind(self, *args, **kwargs):
        self.text_ctrl.Unbind(*args, **kwargs)


    def OnShowPassword(self, _evt):
        """ Handle PW show/hide toggle.
        """
        self.showPassword(None)


    def showPassword(self, show=True):
        """ Show, hide, or toggle the password visibility.

            :param show: `True` to show text, `False` to show dots, `None` to
                toggle.
        """
        is_password = self.hidden

        if show is None:
            show = is_password
        elif (show != is_password):
            return

        current_value = self.text_ctrl.GetValue()
        current_insertion = self.text_ctrl.GetInsertionPoint()
        current_selection = self.text_ctrl.GetSelection()

        if show:
            font, bmp, tt = self.fontVisible, self.bmp_visible, 'Hide Password'
        else:
            font, bmp, tt = self.fontHidden, self.bmp_hidden, 'Show Password'

        self.hidden = not show
        self.text_ctrl.SetValue('')
        self.text_ctrl.SetFont(font)
        self.text_ctrl.SetValue(current_value)
        self.text_ctrl.SetSelection(*current_selection)
        self.text_ctrl.SetInsertionPoint(current_insertion)

        self.staticbmp.SetBitmap(bmp)
        self.staticbmp.SetToolTip(tt)


    # =======================================================================
    # Standard methods that map directly to the inner `TextCtrl`
    # =======================================================================

    def GetValue(self) -> str:
        return self.text_ctrl.GetValue()


    def SetValue(self, value: str):
        self.text_ctrl.SetValue(value)


    def SetToolTop(self, tt: str):
        self.text_ctrl.SetToolTip(tt)


    def GetToolTip(self) -> str:
        return self.text_ctrl.GetToolTip()


    def UnsetToolTip(self):
        self.text_ctrl.UnsetToolTip()


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
    Validate and parse an IP address or hostname, optionally with a port
    number separated by a colon. If the structure of the address is valid,
    the ability to connect will be tested (optional). ``localhost`` is a
    special case, and gets converted to the computer's actual IP.

    :param val: The IP address or hostname, with optional port number separated
        by a colon (e.g., ``192.168.0.1``, ``localhost``, ``192.168.0.1:1883``,
        or ``broker.local:1883``).
    :param defaultPort: The default port number to use (if not included in `val`).
    :param check: If `True`, verify a connection can be made to the address/port.
    :param timeout: Time to wait for the verification check.
    :return: The IP address and the port number.
    """
    try:
        ipMatch = re.match(r"\b(\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?\b", val)
        hostMatch = re.match(r"^(?!.*\.\.)([A-Za-z0-9.-]+)(?::(\d{1,5}))?$", val)
        if not (ipMatch or hostMatch):
            raise ValueError

        ip, port = (ipMatch or hostMatch).groups()
        if ipMatch:
            # This could probably be done in a more complex regular expression:
            if not all(0 <= int(part) <= 255 for part in ip.split('.')):
                raise ValueError

        port = int(port or defaultPort)

    except (AttributeError, ValueError, TypeError):
        raise ValueError(f'Invalid address: {val!r}') from None

    if check:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((ip, port))
        except OSError as err:
            if err.errno == socket.EAI_NODATA:
                raise ValueError(f"Could not resolve hostname: {ip}") from None
            else:
                raise ValueError(f"Could not verify address '{ip}:{port}': {err.strerror}") from None
        except (TimeoutError, ConnectionRefusedError) as err:
            raise ValueError(f"Could not verify address '{ip}:{port}': {err!r}") from None

    return ip, port


# ===========================================================================
#
# ===========================================================================

class IPDialog(sc.SizedDialog):
    """ Simple dialog for entering a broker IP address.
        TODO: OUTDATED, REMOVE THIS
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('style', wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        kwargs.setdefault('title', 'Enter Broker IP')
        super().__init__(*args, **kwargs)

        pane = self.GetContentsPane()
        pane.SetSizerType("form")

        label = wx.StaticText(pane, -1, "Address:")
        label.SetSizerProps(valign='centre')
        self.ipField = wx.TextCtrl(pane, -1,
                                   validator=TextValidator(
                                       validChar=lambda x: x in ('0123456789.:'),
                                       validator=validateIP))
        self.ipField.SetSizerProps(expand=True)

        self.SetButtonSizer(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL))

        self.Fit()
        size = (400, self.GetSize()[1])
        self.SetSize(size)
        self.SetMinSize(size)
        self.ipField.SetFocus()


    def GetValue(self):
        try:
            return parseIP(self.ipField.GetValue())
        except ValueError as err:
            logger.error(f'IPDialog.GetValue() error: {err}')
            return None


class BrokerField(wx.Panel):
    """
    A widget for selecting an MQTT broker, either from advertising or
    a manually-entered IP address.

    TODO: OUTDATED, REMOVE THIS

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


    def updateList(self, scan=True):
        """ Scan for mDNS advertised brokers and update the display.
        """
        try:
            self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
            self.brokerBtn.Enable(False)
            self.brokerScanBtn.Enable(False)

            name = self.GetString()

            if scan:
                self.brokers = {b['name']: b for b in findBrokers(None, **self.scanKwargs)}

            self.names = sorted(self.brokers)
            if self.userIp:
                addr, port = self.userIp
                self.brokers[f'{addr}:{port}'] = {
                    'name': f'{addr}:{port}',
                    'serviceType': '_endaq._tcp.local.',
                    'host': [addr],
                    'port': port,
                    'properties': {}}
                self.names.append(f'{addr}:{port}')

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
        logger.debug(f'Posting broker change: {self.selectedName} -> {self.GetValue()}')

        # TODO: Make sure this works when called through enDAQ Lab, etc.
        dest = wx.GetActiveWindow()
        wx.PostEvent(dest, EvtBrokerUpdate(broker=self.GetValue()))


    def showIpDialog(self):
        with IPDialog(self) as dlg:
            q = dlg.ShowModal()
            if q != wx.ID_OK:
                return
            ip = dlg.GetValue()
            if ip:
                self.userIp = ip
                self.setSelectedName(f'{ip[0]}:{ip[1]}')
                self.updateList(scan=False)


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

        menu.AppendSeparator()
        menu.Append(self.ID_USER_BROKER, 'Enter IP Address')
        self.PopupMenu(menu)
        menu.Destroy()


    def OnBrokerSelection(self, evt):
        """ Handle broker selection.
        """
        mid = evt.GetId()
        if mid == self.ID_USER_BROKER:
            self.showIpDialog()
        elif mid in self.brokersByItemID:
            txt = self.brokersByItemID[mid]
            if txt != self.selectedName:
                self.setSelectedName(txt)
                self.postSelectionEvent()


    def GetValue(self) -> Dict[str, Any]:
        """ Get the info dictionary for the selected broker.
        """
        return self.brokers.get(self.selectedName, None)


    def GetString(self) -> str:
        """ Get the currently selected broker name/IP.
        """
        return self.selectedName


    def IsValid(self) -> bool:
        """ Is the currently-selected broker name/address valid?
        """
        broker = self.GetValue()
        return bool(broker)


#===============================================================================
#
#===============================================================================

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


#===============================================================================
# Field validators
#===============================================================================

def validateIP(value: str):
    try:
        _ = parseIP(value, check=True)
        return True
    except ValueError as err:
        raise FieldValidationError(str(err))


#===============================================================================
#
#===============================================================================

class KeepAliveCallback:
    """
    A somewhat simplistic device command callback that is intended to prevent
    long-running commands in the main thread from getting the GUI flagged
    as 'Not Responding.'

    Use:
        cb = KeepAliveCallback()
        device.command.setWifi(data, callback=cb)

    TODO: Determine if this actually works reliably
    """

    def __init__(self, interval: float = 4.5):
        self.interval = interval
        self.nextUpdate = time() + interval


    def __call__(self, *args, **kwargs):
        """ Callback that kicks the GUI. Always returns `False` (don't cancel).
        """
        if time() > self.nextUpdate:
            wx.Yield()
            self.nextUpdate = time() + self.interval
        return False
