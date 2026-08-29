"""
Special button widgets that execute device commands instead of modifying
config item values.
"""

import logging

import wx

from .base import ConfigWidget
from .base import registerField
from .common import isCompiled
from .widgets.controls import NewControlButtons
from .widgets.shared import promptDeviceReboot, promptDeviceShutdown, ExtraMessageBox

logger = logging.getLogger(__file__)


# ===============================================================================
# Command buttons
# ===============================================================================

@registerField
class CheckDriftButton(ConfigWidget):
    """ Special-case "field" consisting of a button that checks the recorder's
        clock versus the host computer's time. It does not affect the config
        data.
    """
    UNITS = False
    DEFAULT_TYPE = None

    DEFAULT_LABEL = "Check Clock Drift"
    DEFAULT_TOOLTIP = "Read the recorder's clock and compare to the current system time."


    def __init__(self, *args, **kwargs):
        """ Constructor.

            :see: `ConfigWidget.__init__()`
        """
        self.setAttribDefault("label", self.DEFAULT_LABEL)
        self.setAttribDefault("tooltip", self.DEFAULT_TOOLTIP)
        super(CheckDriftButton, self).__init__(*args, **kwargs)


    def initUI(self):
        """ Build the user interface, adding the item label and/or checkbox,
            the appropriate UI control(s) and a 'units' label (if applicable).
            Separated from `__init__()` for the sake of subclassing.
        """
        self.checkbox = None
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.field = wx.Button(self, -1, self.label)
        self.sizer.Add(self.field, 0)

        if self.tooltip:
            self.SetToolTip(self.tooltip)
            self.field.SetToolTip(self.tooltip)

        self.SetSizer(self.sizer)

        self.Bind(wx.EVT_BUTTON, self.OnButtonPress)


    def OnButtonPress(self, evt):
        """ Handle button press: perform the clock drift test.
        """
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        try:
            times = self.root.device.getTime()
        except Exception:
            if self.root.DEBUG and not isCompiled():
                raise
            self.showError("Could not read the recorder's clock!", self.label,
                           style=wx.OK | wx.ICON_ERROR)
            return

        drift = times[0] - times[1]
        msg = "Recorder is %.4f seconds %s the computer." % \
              (drift, "behind" if drift > 0 else "ahead of")

        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
        wx.MessageBox(msg, self.label, parent=self, style=wx.OK | wx.ICON_INFORMATION)


@registerField
class ResetButton(CheckDriftButton):
    """ Special-case "field" that consists of a button that resets all its
        sibling fields in its group or tab. Not to be confused with
        `RebootButton`, which actually resets the hardware.
    """

    DEFAULT_LABEL = "Reset to Defaults"
    DEFAULT_TOOLTIP = "Reset this set of fields to their default values"


    def OnButtonPress(self, evt):
        """ Handle button press: reset sibling fields to the factory defaults.
        """
        if self.group is not None:
            self.group.setToDefault()


# ===============================================================================
# Reboot/reset buttons
# ===============================================================================

@registerField
class RebootButton(CheckDriftButton):
    """ Special-case "field" that consists of a button that sends a reset
        command to the device.
    """

    DEFAULT_LABEL = "Reset/Reboot Device"
    DEFAULT_TOOLTIP = "Send a shutdown/power off command to the device"

    _ICON_IDX = 8
    WHAT = 'device reset/reboot'

    def __init__(self, *args, **kwargs):
        """ Constructor.

            :see: `ConfigWidget.__init__()`
        """
        super().__init__(*args, **kwargs)
        self._command = promptDeviceReboot


    def initUI(self):
        self.checkbox = None
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.field = wx.Button(self, -1, self.label)
        self.field.SetToolTip(self.tooltip)

        NewControlButtons._loadImages()
        icons = NewControlButtons.ICONS[self._ICON_IDX]
        self.field.SetBitmap(icons[0], wx.LEFT)
        self.field.SetBitmapCurrent(icons[0])
        self.field.SetBitmapPressed(icons[2])
        self.field.SetBitmapDisabled(icons[3])
        self.field.SetBitmapMargins((0, 0))

        self.sizer.Add(self.field, 1, wx.EXPAND)
        self.SetSizer(self.sizer)
        self.Bind(wx.EVT_BUTTON, self.OnButtonPress)


    def OnButtonPress(self, evt):
        """ Handle button press: reset sibling fields to the factory defaults.
        """
        if self._command is None:
            logger.debug("No function attached to button; no device?")
            return

        if self.root.configChanged():
            q = wx.MessageBox(
                    "Discard changes?\n\n"
                    'Some configuration changes may not have been applied. '
                    f'Execute {self.WHAT} without saving them?',
                    self.WHAT.capitalize(),
                    style=(wx.YES | wx.NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_INFORMATION),
                    parent=self.root)
            if q == wx.CANCEL:
                return
            elif q == wx.YES:
                # TODO: save config here
                self.root.saveConfigData()
            else:
                # If cancelled, the returned configuration data is `None`
                self.configData = None

        if thread := self._command(self.root.device, self.root):
            wx.MilliSleep(100)  # Just to make sure the command executed
            while thread.is_alive():
                if thread.failed.set():
                    # TODO: Improved error dialog content based on failure type
                    msg = f"An error occurred while executing {self.WHAT}"
                    err = ''
                    if thread.failure:
                        err = f'Error: {thread.failure!r}'

                    ExtraMessageBox(msg, "Error", err)
                    return
                wx.Yield()
                wx.MilliSleep(100)

            # Changes already saved, end with CANCEL
            self.root.EndModal(wx.ID_CANCEL)


@registerField
class ShutdownButton(RebootButton):
    """ Special-case "field" that consists of a button that sends a
        shutdown/power off command command, intended for use with a
        Gateway.
    """

    DEFAULT_LABEL = "Power Off"
    DEFAULT_TOOLTIP = "Send a shutdown/power off command to the device"

    _ICON_IDX = 9
    WHAT = 'device shutdown'

    def __init__(self, *args, **kwargs):
        """ Constructor.

            :see: `ConfigWidget.__init__()`
        """
        super().__init__(*args, **kwargs)
        self._command = promptDeviceShutdown
