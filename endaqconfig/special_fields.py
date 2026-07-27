"""
Special button widgets that execute device commands instead of modifying
config item values.
"""

import logging

import wx

from endaq.device.mqtt.discovery import findBrokers

from endaqconfig.base import EnumField, EnumOption, FloatField, TextField
from endaqconfig.base import registerField
from endaqconfig.common import getUtcOffset
from endaqconfig.validators import TextValidator
from endaqconfig.widgets.shared import PasswordTextCtrl

logger = logging.getLogger(__file__)


@registerField
class ServiceNameField(TextField):
    """ UI widget for entering the name of an mDNS service, either manually or
        by selecting an advertised one. EBML ID: 0x4045
    """

    def __init__(self, *args, **kwargs):
        """ Constructor.

            :see: `ConfigWidget.__init__()`
        """
        self.setAttribDefault("label", "mDNS Instance Name")
        self.oldvalue = ''
        super().__init__(*args, **kwargs)


    def addField(self):
        """ Class-specific method for adding the appropriate type of widget.
        """
        self.field = wx.ComboBox(self, -1, style=wx.CB_DROPDOWN)

        # Notice that this event is only supported by wxMSW, wxGTK with GTK+ 2.10 or later, and OSX/Cocoa.
        self.Bind(wx.EVT_COMBOBOX_DROPDOWN, self.OnDropDown)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, self.OnCloseUp)

        self.sizer.Add(self.field, 4, wx.EXPAND)
        return self.field


    def OnDropDown(self, evt):
        """ Handle list opening event.
        """
        self.oldvalue = self.field.GetValue()

        try:
            wx.SetCursor(wx.Cursor(wx.CURSOR_ARROWWAIT))
            brokers = findBrokers(None, persistent=True)
            self.brokers = {broker.name: broker for broker in brokers}
            self.field.SetItems(sorted(self.brokers))
        finally:
            wx.SetCursor(wx.NullCursor)

        evt.Skip()


    def OnCloseUp(self, evt):
        """ Handle list closing event.
        """
        if not self.field.GetValue():
            # Restore previous value if nothing selected
            self.field.SetValue(self.oldvalue)
        evt.Skip()


@registerField
class CheckServiceNameField(ServiceNameField):
    """ UI widget (with a checkbox) for entering/selecting mDNS services.
    """
    CHECK = True


# ===============================================================================

@registerField
class BitField(EnumField):
    """ A widget representing a set of bits in an unsigned integer, with
        individual checkboxes for each bit. A subclass of `EnumField`, each
        `EnumOption` creates a checkbox; its value indicates the index of the
        corresponding bit (0 is the first bit, 1 is the second, 2 is the third,
        etc.).
    """
    DEFAULT_TYPE = "UIntValue"


    def addField(self):
        """ Class-specific method for adding the appropriate type of widget.
        """
        if self.labelWidget is None:
            # No label or checkbox; add checks directly to main sizer.
            childSizer = self.sizer
        else:
            # the field has a label or a checkbox; indent child checkboxes.
            childSizer = wx.BoxSizer(wx.VERTICAL)
            self.sizer.Add(childSizer, 1, wx.WEST, 24)

        for o in self.options:
            o.default = (self.default >> o.value) & 1
            o.checkbox = wx.CheckBox(self, -1, o.label)
            childSizer.Add(o.checkbox, 0,
                           wx.ALIGN_LEFT | wx.EXPAND | wx.NORTH | wx.SOUTH, 4)

            tooltip = o.tooltip or self.tooltip
            if tooltip:
                o.checkbox.SetToolTip(tooltip)

        self.field = None
        return childSizer


    def setDisplayValue(self, val, check=True):
        """ Check the items according to the bits of the supplied value.
        """
        for o in self.options:
            o.checkbox.SetValue(bool(val & (1 << o.value)))
        self.setCheck(check)


    def initUI(self):
        """ Build the user interface, adding the item label and/or checkbox,
            the appropriate UI control(s) and a 'units' label (if applicable).
            Separated from `__init__()` for the sake of subclassing.
        """
        optionEls = [el for el in self.element.value if el.name == "EnumOption"]
        self.options = [EnumOption(el, self, n) for n, el in enumerate(optionEls)]

        self.sizer = wx.BoxSizer(wx.VERTICAL)

        if self.label:
            if self.CHECK:
                self.checkbox = wx.CheckBox(self, -1, self.label or '')
                self.labelWidget = self.checkbox
                self.sizer.Add(self.checkbox, 0)  # , wx.ALIGN_CENTER_VERTICAL)
                self.Bind(wx.EVT_CHECKBOX, self.OnCheck)
                self.setCheck(False)
            else:
                self.checkbox = None
                self.labelWidget = wx.StaticText(self, -1, self.label or '')
                self.sizer.Add(self.labelWidget, 0)  # , wx.ALIGN_CENTER_VERTICAL)

            self.labelWidget.SetFont(self.labelWidget.GetFont().Bold())
        else:
            self.checkbox = self.labelWidget = None

        self.addField()
        self.unitLabel = None

        if self.tooltip:
            self.SetToolTip(self.tooltip)
            if self.labelWidget is not None:
                self.labelWidget.SetToolTip(self.tooltip)

        self.SetSizer(self.sizer)

        self.setToDefault()

        # Child checks should also fire the 'on check' handler.
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck)


    def getDisplayValue(self):
        """ Get the field's displayed value.
        """
        if self.checkbox is not None and not self.checkbox.GetValue():
            return None
        if self.isDisabled():
            return None

        val = 0
        for o in self.options:
            if o.checkbox.GetValue():
                val = val | (1 << o.value)

        return val


    def updateDisabled(self):
        """ Automatically enable or disable this field according to its
            `isDisabled` expression (if any). Individually disabled options
            get set to their default.
        """
        super(BitField, self).updateDisabled()

        if not self.isDisabled():
            for o in self.options:
                dis = o.isDisabled()
                o.checkbox.Enable(not dis)
                if dis:
                    o.checkbox.SetValue(bool(o.default))


@registerField
class CheckBitField(BitField):
    """ A widget (with a checkbox) representing a set of bits in an unsigned
        integer, with individual checkboxes for each bit. A subclass of
        `EnumField`, each `EnumOption` creates a checkbox; its value indicates
        the index of the corresponding bit (0 is the first bit, 1 is the
        second, 2 is the third, etc.).
    """
    CHECK = True


# ===============================================================================

@registerField
class UTCOffsetField(FloatField):
    """ Special-case UI widget for entering the local UTC offset, with the
        ability to get the value from the computer.
    """
    DEFAULT_TYPE = "IntValue"


    def __init__(self, *args, **kwargs):
        """ Constructor.

            :see: `ConfigWidget.__init__()`
        """
        self.setAttribDefault('min', -23.0)
        self.setAttribDefault('max', 23.0)
        self.setAttribDefault('units', "Hours")
        self.setAttribDefault('increment', 0.5)
        self.setAttribDefault('displayFormat', "x/3600.0")
        self.setAttribDefault('valueFormat', "x*3600")
        self.setAttribDefault("label", "Local UTC Offset")
        super(UTCOffsetField, self).__init__(*args, **kwargs)


    def initUI(self):
        """ Build the user interface, adding the item label and/or checkbox,
            the appropriate UI control(s) and a 'units' label (if applicable).
            The UTC Offset fields have an extra button to the right of the
            units label.
        """
        super(UTCOffsetField, self).initUI()

        self.getOffsetBtn = wx.Button(self, -1, "Get Local Offset")
        self.getOffsetBtn.SetSize(-1, self.field.GetSize()[1])
        self.getOffsetBtn.Bind(wx.EVT_BUTTON, self.OnSetTZ)
        self.sizer.Add(self.getOffsetBtn, 0)

        if self.tooltip:
            self.getOffsetBtn.SetToolTip(self.tooltip)


    def OnSetTZ(self, _evt):
        """ Handle the 'Get Local Offset' button press by getting the local
            time zone offset.
        """
        self.setDisplayValue(getUtcOffset())


    def getConfigValue(self):
        """ Get the widget's value, as written to the config file.
        """
        val = super().getConfigValue()
        if val is None:
            return None
        return int(val)


@registerField
class CheckUTCOffsetField(UTCOffsetField):
    """ Special-case UI widget (with a checkbox) for entering the local UTC
        offset, with the ability to get the value from the computer.
    """
    CHECK = True


# ===============================================================================

@registerField
class PasswordField(TextField):
    """ UI widget for editing a password.
    """

    def __init__(self, *args, **kwargs):
        """ Constructor.

            :see: `ConfigWidget.__init__()`
        """
        self.setAttribDefault("label", "Password")
        super().__init__(*args, **kwargs)


    def addField(self):
        """ Class-specific method for adding the appropriate type of widget.
        """
        validator = TextValidator(self.isValid, minLen=self.minLength, maxLen=self.maxLength)
        self.field = PasswordTextCtrl(self, -1, str(self.default or ''),
                                      validator=validator)

        self.field.Bind(wx.EVT_KILL_FOCUS, self.OnExitField)
        self.sizer.Add(self.field, 4, wx.EXPAND)
        return self.field


@registerField
class CheckPasswordField(PasswordField):
    """ UI widget (with a checkbox) for editing passwords.
    """
    CHECK = True


# ===============================================================================
# --- Type-specific fields/widgets
# Minor variations of existing fields with specific purposes, providing various
# defaults (labels, units, range, etc.) that then do not need to be specified
# in the CONFIG.UI data.
#
# These few are mostly proof-of-concept and don't provide additional features.
# Future ones may offer special handling (selectable units, etc).
# ===============================================================================

@registerField
class FloatTemperatureField(FloatField):
    """ `FloatField` variant with appropriate defaults for temperature display.
    """


    def __init__(self, *args, **kwargs):
        """ Constructor.

            :see: `ConfigWidget.__init__()`
        """
        self.setAttribDefault("units", u"\u00b0C")
        self.setAttribDefault("label", "Temperature")
        self.setAttribDefault("min", -40.0)
        self.setAttribDefault("max", 80.0)
        super(FloatTemperatureField, self).__init__(*args, **kwargs)


@registerField
class CheckFloatTemperatureField(FloatTemperatureField):
    """ `CheckFloatField` variant with appropriate defaults for temperature
        display.
    """
    CHECK = True


@registerField
class FloatAccelerationField(FloatField):
    """ `FloatField` variant with appropriate defaults for acceleration display.
    """


    def __init__(self, *args, **kwargs):
        """ Constructor.

            :see: `ConfigWidget.__init__()`
        """
        self.setAttribDefault("units", u"g")
        self.setAttribDefault("label", "Acceleration")
        self.setAttribDefault("min", -100.0)
        self.setAttribDefault("max", 100.0)
        self.setAttribDefault("default", 5.0)
        super(FloatAccelerationField, self).__init__(*args, **kwargs)


@registerField
class CheckFloatAccelerationField(FloatAccelerationField):
    """ `CheckFloatField` variant with appropriate defaults for acceleration
        display.
    """
    CHECK = True
