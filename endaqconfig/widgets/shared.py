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
from typing import Callable, Optional, Tuple

import wx
import wx.adv
import wx.lib.masked as wx_mc

from endaq.device import Recorder

from endaqconfig.common import isGateway
from endaqconfig.validators import FieldValidationError
from endaqconfig.widgets.threads import DeviceCommandThread
from endaqconfig.widgets.controls import getStatusDisplay
from endaqconfig.widgets.icons import pw_show, pw_hide

logger = logging.getLogger(__name__)


#===============================================================================
# Resources: non-Python files.
#===============================================================================

# This can/will be modified when incorporated into other projects.
# Always combine RESOURCES_PATH with resource filenames just before use.
RESOURCES_PATH = os.path.dirname(__file__)

FONTFILE = 'password-dots.ttf'
FONTNAME = 'Password Dots'


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

        wx.Font.AddPrivateFont(os.path.join(RESOURCES_PATH, FONTFILE))
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


    def showPassword(self, show: Optional[bool] = True):
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


    def GetToolTip(self) -> wx.ToolTip:
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
            # wx.Point *does* implement __add__!
            # noinspection PyUnresolvedReferences
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
            timeout: float = 0.5) -> Tuple[str, int]:
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
        except TimeoutError as err:
            logger.error(f"Error validating '{ip}:{port}': {err!r}")
            raise ValueError(f"Could not verify address '{ip}:{port}' (timed out)") from None
        except OSError as err:
            logger.error(f"Error validating '{ip}:{port}': {err!r}")
            if err.errno == socket.EAI_NODATA:
                raise ValueError(f"Could not resolve hostname: '{ip}'") from None
            elif err.strerror:
                raise ValueError(f"Could not verify address '{ip}:{port}': {err.strerror}") from None
            else:
                raise ValueError(f"Could not verify address '{ip}:{port}'") from None

    return ip, port


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

    TODO: Determine if this actually works reliably, without adverse side effects
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


#===============================================================================
#
#===============================================================================

def promptDeviceReboot(device: Recorder,
                       parent: Optional[wx.Window] = None,
                       callback: Optional[Callable] = None) -> DeviceCommandThread:
    """ Send a reset/reboot command to a device. If the device is a Gateway,
        prompt the user to confirm, and tell them to disconnect USB (so the
        CompuLab-based Gateway doesn't go into recovery 'bootloader' mode.

        :param device: The enDAQ device to reboot.
        :param parent: The parent window, for positioning the dialog (if shown).
        :param callback: A callback function for `CommandInterface.reset()`
            (see `endaq.device.command_interfaces`).
        :returns: A `DeviceCommandThread` running the `CommandInterface.reset()`
            command.
    """
    if isGateway(device):
        q = wx.MessageBox(
                f'Reboot/Reset {device.productName}?\n\n'
                'This will disrupt communication with any device connected to it.',
                'Reset',
                style=wx.ICON_WARNING | wx.YES_NO | wx.YES_DEFAULT,
                parent=parent)

        if q != wx.YES:
            logger.debug('No reset for the wicked!')
            return None

    logger.debug(f'Sending reboot to {device}')
    thread = DeviceCommandThread(device, device.command.reset,
                                 callback=callback)

    # This will need revising if we use different hardware
    if isGateway(device) and 'MQTT' not in type(device.command).__name__:
        wx.MessageBox('Unplug Gateway USB cable now!\n\n'
                      'The Gateway must not have a USB connection when booting.',
                      'Disconnect USB',
                      style=wx.ICON_WARNING | wx.OK,
                      parent=parent)

    return thread


def promptDeviceShutdown(device: Recorder,
                         parent: Optional[wx.Window] = None,
                         callback: Optional[Callable] = None) -> DeviceCommandThread:
    """ Prompt the user to confirm before sending a shutdown command to a
        device (presumably a Gateway).

        :param device: The enDAQ device to shut down/power off.
        :param parent: The parent window, for positioning the dialog (if shown).
        :param callback: A callback function for `CommandInterface.shutdown()`
            (see `endaq.device.command_interfaces`).
        :returns: A `DeviceCommandThread` running the `CommandInterface.shutdown()`
            command.
    """
    q = wx.MessageBox(
            f'Shutdown/power off {device.productName}?\n\n'
            'This will disrupt communication with any device connected to it.',
            'Power Off',
            style=wx.ICON_WARNING | wx.YES_NO | wx.YES_DEFAULT,
            parent=parent)

    if q != wx.YES:
        logger.debug('Never gonna give you up, never gonna shut you down')
        return None

    logger.debug(f'Sending shutdown to {device}')
    thread = DeviceCommandThread(device, device.command.shutdown,
                                 callback=callback)
    return thread


# ===============================================================================
#
# ===============================================================================

# noinspection PyUnusedLocal
def ExtraMessageBox(message: str,
                    caption: str = wx.MessageBoxCaptionStr,
                    extra: str = '',
                    style: int = wx.OK | wx.CENTRE,
                    parent: Optional[wx.Window] = None,
                    x: int = wx.DefaultCoord,
                    y: int = wx.DefaultCoord) -> int:
    """ A drop-in replacement for `wx.MessageBox()` with an extended message
        (e.g., a verbose error). It takes the same arguments, plus `extra`,
        minus the `x` and `y` position arguments (ignored under MSW, anyway,
        left in for compatibility).

        :param message: Message to show in the dialog.
        :param caption: The dialog title.
        :param extra: The error message.
        :param style: Combination of style flags described in wx.MessageDialog
            documentation.
        :param parent: The parent window.
        :param x: Horizontal dialog position (ignored under MSW).
        :param y: Vertical dialog position (ignored under MSW).
        :returns: `wx.YES`, `wx.NO`, `wx.CANCEL`, `wx.OK` or `wx.HELP` (notice
            that this return value is different from the return value of
            `wx.MessageDialog.ShowModal`).
    """
    with wx.RichMessageDialog(parent, message, caption, style=style) as dlg:
        if extra:
            dlg.ShowDetailedText(extra)
        result = dlg.ShowModal()

        return {wx.ID_OK: wx.OK,
                wx.ID_CANCEL: wx.CANCEL,
                wx.ID_YES: wx.YES,
                wx.ID_NO: wx.NO,
                wx.ID_HELP: wx.HELP}.get(result, wx.ID_OK)


# ===============================================================================
#
# ===============================================================================

def showError(msg: str,
              caption: str,
              style: int = wx.OK | wx.OK_DEFAULT | wx.ICON_ERROR,
              err: Optional[Exception] = None,
              parent: Optional[wx.Window] = None):
    """ Show an error message. Wraps the standard message box to add some
        debugging stuff.
    """
    if not msg.endswith(('.', '!', '?')):
        msg += "."

    extra = ''
    if isinstance(err, Exception):
        extra = f'{type(err).__name__}: {err}'
    elif err:
        extra = str(err)

    q = ExtraMessageBox(msg, caption, style=style, parent=parent,
                        extra=extra)
    if err is not None:
        logger.debug("%s: %r" % (msg, err))
        if wx.GetKeyState(wx.WXK_CONTROL) and wx.GetKeyState(wx.WXK_SHIFT):
            raise

    return q
