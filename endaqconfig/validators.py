"""
Validation: `wx.Validator` subclasses and various validation functions
used by them.
"""

from typing import Any, Callable, TYPE_CHECKING
import wx

from .common import getClipboardText

if TYPE_CHECKING:
    from .config_dialog import ConfigDialog

# ===========================================================================
#
# ===========================================================================

VALIDATORS: dict[str, Callable[[Any, "ConfigDialog"], None]] = {}


def validator(func):
    """ Class decorator for registering a validation function.
    """
    global VALIDATORS
    VALIDATORS[func.__name__] = func
    return func


# ===========================================================================
#
# ===========================================================================

class FieldValidationError(Exception):
    """ Raised when a validator fails. """


# ===========================================================================
# Widget validators
# ===========================================================================

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

        tooltip = win.GetToolTipText().partition('⚠')[0].strip()
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
# Field validation functions. Used in the rendered CONFIG.UI, function names
# match values of ``Validator`` elements in the CONFIG.UI data.
# ===========================================================================

@validator
def mDNS(value: str, root: "ConfigDialog"):
    """ For an MQTT Device Manager/Gateway: Validate an mDNS name, ensuring
        it is unique.

        :raises FieldValidationError:

        :param value: The mDNS name to validate.
        :param root: The `ConfigDialog` instance. For accessing config
            values, fields in special tabs, etc.
    """
    # TODO: Call `endaq.device.mqtt.discovery.findBrokers(None)`, ignore
    #  the Gateway's own advertised mDNS name.
    pass
