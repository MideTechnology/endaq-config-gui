"""
New, modular configuration system. Dynamically creates the UI based on the new
"UI Hints" data. The UI is described in EBML; UI widget classes have the same
names as the elements. The crucial details of the widget type are also encoded
into the EBML ID; if there is not a specialized subclass for a particular
element, this is used to find a generic widget for the data type.

Basic theory of operation:

* Configuration items with values of `None` do not get written to the config
    file.
* Fields with checkboxes have a value of `None` if unchecked.
* Disabled fields also have a value of `None`.
* Children of disabled fields have a value of `None`, as do children of fields
    with checkboxes (i.e. `CheckGroup`) if their parent is unchecked.
* The default value for a field is in the native units/data type as in the
    config file. Setting a field to the default uses the same mechanism as
    setting it according to the config file.
* Fields with values that aren't in the config file get the default; if they
    have checkboxes, the checkbox is left unchecked.

:todo: Clean up (maybe replace) the old calibration and info tabs.
:todo: There are some redundant calls to update enabled and checkbox states.
    They don't cause a problem, but they should be cleaned up.
"""

import errno
import logging
import os
from typing import Any, Dict, Optional, Union

import wx
import wx.lib.sized_controls as SC

from ebmlite import loadSchema
import endaq.device
from endaq.device import Recorder, configio

from .base import logger
from . import base
from .common import isCompiled
from .widgets import icons

# Widgets. Even though these modules aren't used directly, they need to be
# imported so that their contents can get into the `base.TAB_TYPES` dictionary.
from . import special_tabs
from . import wifi_tab

# ===============================================================================
#
# ===============================================================================

__DEBUG__ = False

# ===============================================================================
#
# ===============================================================================


class ConfigDialog(SC.SizedDialog):
    """ Root window for recorder configuration.
    """
    # Used by the Info tab. Remove after refactoring the legacy tabs.
    ICON_INFO = 0
    ICON_WARN = 1
    ICON_ERROR = 2

    EXPORT_TOOLTIPS = (
        None,  # No Wi-Fi or cal
        "Does not include user calibration.",
        "Does not include Wi-Fi AP configuration.",
        "Does not include calibration or Wi-Fi AP configuration."
    )


    def __init__(self, *args, **kwargs):
        """ Constructor. Takes standard `SizedDialog` arguments, plus:

            :param device: The recorder to configure (an instance of a
                `endaq.device.Recorder` subclass)
            :param setTime: If `True`, the 'Set device clock on exit'
                checkbox will be checked by default.
            :param saveOnOk: If `False`, exiting the dialog with OK will not
                save to the recorder. Primarily for debugging.
        """
        self.schema = loadSchema('mide_config_ui.xml')

        self.setTime: bool = kwargs.pop('setTime', True)
        self.device: Optional[Recorder] = kwargs.pop('device', None)
        self.saveOnOk: bool = kwargs.pop('saveOnOk', True)
        self.useUtc: bool = kwargs.pop('useUtc', True)
        self.showAdvanced: bool = kwargs.pop('showAdvanced', False)
        self.DEBUG: bool = kwargs.pop('debug', __DEBUG__)
        icon = kwargs.pop('icon', None)

        self.postConfigMessage = None

        if self.DEBUG:
            # May be redundant when running standalone, but just in case:
            logger.setLevel(logging.DEBUG)

        try:
            devName = self.device.productName
            if self.device.path:
                devName += (" (%s)" % self.device.path)
        except AttributeError:
            # Typically, this won't happen outside of testing.
            devName = "Recorder"

        kwargs.setdefault("title", f"Configure {devName}")
        kwargs.setdefault("style", wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        super(ConfigDialog, self).__init__(*args, **kwargs)

        icon = icons.icon.GetIcon() if icon is None else icon
        if icon:
            self.SetIcon(icon)

        pane = self.GetContentsPane()
        self.notebook = wx.Notebook(pane, -1)
        self.notebook.SetSizerProps(expand=True, proportion=-1)

        self.configData = {}
        self.origConfigData = {}

        self.configItems = {}
        self.configValues = base.ConfigContainer(self)
        self.displayValues = base.DisplayContainer(self)

        # Variables to be accessible by field expressions. Includes mapping
        # None to ``null``, making the expressions less specific to Python.
        self.expressionVariables = {'Config': self.displayValues,
                                    'null': None}

        self.tabs = []

        self.wifiTab = None
        self.hasCal = False

        self.hints = self.device.config.getConfigUI()
        self.buildUI()
        self.loadConfigData()

        # check_box_sizer = wx.BoxSizer(wx.HORIZONTAL)
        check_box_sizer = SC.SizedPanel(pane, -1)
        check_box_sizer.SetSizerType("horizontal")
        check_box_sizer.SetSizerProps(expand=True)

        self.setClockCheck = wx.CheckBox(check_box_sizer, -1, "Set device clock on exit")
        self.setClockCheck.SetSizerProps(expand=True, border=(['top', 'bottom'], 8))

        SC.SizedPanel(check_box_sizer, -1).SetSizerProps(proportion=1)  # Spacer

        if self.device.hasWifi:
            self.applyWifiChangesCheck = wx.CheckBox(check_box_sizer, -1, "Apply Wi-Fi changes on exit")
            self.applyWifiChangesCheck.SetSizerProps(halign='right', expand=True, border=(['top', 'bottom'], 8))
            # self.applyWifiChangesCheck.SetValue(True)
        else:
            self.applyWifiChangesCheck = None

        buttonpane = SC.SizedPanel(pane, -1)
        buttonpane.SetSizerType("horizontal")
        buttonpane.SetSizerProps(expand=True)  # , border=(['top'], 8))

        self.importBtn = wx.Button(buttonpane, -1, "Import...")
        self.exportBtn = wx.Button(buttonpane, -1, "Export...")

        exportTT = "Export device configuration data."
        importTT = "Import device configuration data."

        x = (0b10 if self.wifiTab is not None else 0) | self.hasCal
        if x:
            exportTT = f"{exportTT}\n{self.EXPORT_TOOLTIPS[x]}"
            importTT = f"{importTT}\n{self.EXPORT_TOOLTIPS[x]}"

        self.exportBtn.SetToolTip(exportTT)
        self.importBtn.SetToolTip(importTT)

        SC.SizedPanel(buttonpane, -1).SetSizerProps(proportion=1)  # Spacer
        wx.Button(buttonpane, wx.ID_OK)
        wx.Button(buttonpane, wx.ID_CANCEL)
        buttonpane.SetSizerProps(halign='right')

        self.setClockCheck.SetValue(self.setTime)
        self.setClockCheck.Enable(hasattr(self.device, 'setTime'))

        self.SetAffirmativeId(wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=wx.ID_CANCEL)

        # Restore the following if/when import and export are fixed.
        self.importBtn.Bind(wx.EVT_BUTTON, self.OnImportButton)
        self.exportBtn.Bind(wx.EVT_BUTTON, self.OnExportButton)

        self.Fit()
        self.SetMinSize((500, 480))
        self.SetSize((620, 700))
        wx.SetCursor(wx.Cursor(wx.CURSOR_ARROW))


    def buildUI(self):
        """ Construct and populate the UI based on the ConfigUI element.
        """
        try:
            rootEl = self.hints[0]
        except IndexError:
            raise endaq.device.ConfigError('No CONFIG.UI data for {}'.format(self.device))

        for el in rootEl:
            if el.name in base.TAB_TYPES:
                tabType = base.TAB_TYPES[el.name]
                tab = tabType(self.notebook, -1, element=el, root=self)

                if tabType == wifi_tab.WiFiSelectionTab:
                    self.wifiTab = tab

                self.hasCal = self.hasCal or isinstance(tab, special_tabs.FactoryCalibrationTab)

                if not tab.isAdvancedFeature or self.showAdvanced:
                    self.notebook.AddPage(tab, str(tab.label))
                    self.tabs.append(tab)

            elif el.name == "PostConfigMessage":
                self.postConfigMessage = el.value


    def loadConfigUI(self):
        """ Read the UI definition from the device. For recorders with old
            firmware that doesn't generate a UI description, an appropriate
            generic version is created.
        """
        self.hints = self.device.config.getConfigUI()


    def applyConfigData(self, data: Dict[int, Any], reset: bool = False):
        """ Apply a dictionary of configuration data to the UI.

            :param data: The dictionary of config values, keyed by ConfigID.
            :param reset: If `True`, reset all the fields to their defaults
                before applying the configuration data.
        """
        if reset:
            for c in self.configItems.values():
                c.setToDefault()

        for k, v in data.items():
            try:
                self.configItems[k].setConfigValue(v)
            except KeyError:
                logger.info(f"Item {hex(k)} in config file not in UI, probably okay.")
            except AttributeError as err:
                logger.warning("Unexpected {} in ConfigDialog.applyConfigData(): {}"
                               .format(type(err).__name__, err))

        self.updateDisabledItems()


    def loadConfigData(self):
        """ Load config data from the recorder.
        """
        # Mostly for testing. Will probably be removed.
        if self.device is None:
            self.configData.clear()
            self.origConfigData.clear()
        else:
            self.configData = self.device.config.getConfigValues(original=True)
            self.origConfigData = self.configData.copy()

        self._wifiEnabled = self.configData.get(0x18ff7f, None)

        self.applyConfigData(self.configData)
        return self.configData


    def updateConfigData(self):
        """ Update the dictionary of configuration data.
        """
        self.configData.clear()
        self.configData.update(self.configValues.toDict())


    def updateDeviceConfig(self):
        """ Apply the config dialog's values to the `Recorder`.
        """
        # Clear device's config data (except unknown config values from file)
        for item in self.device.config.items.values():
            item.value = None

        self.updateConfigData()
        for k, v in self.configData.items():
            if k in self.device.config.items:
                self.device.config.items[k].configValue = v
                self.device.config.items[k].changed = True


    def encodeConfigData(self):
        """ Build an EBML-encodeable set of nested dictionaries containing the
            dialog's configuration values. Part of configuration export.
        """
        # FUTURE: Move all import/export into endaq.device
        self.updateDeviceConfig()
        return self.device.config._makeConfig()


    def saveConfigData(self):
        """ Save edited config data to the recorder.
        """
        maxVersion = max(self.device.config.supportedConfigVersions)
        version = self.device.config.configVersionRead or maxVersion
        if version < maxVersion:
            if version in self.device.config.supportedConfigVersions:
                # Prompt to save in old version.
                q = wx.MessageBox("Update configuration file version?\n\n"
                  f"The configuration data loaded from the device used an outdated format (v{version}).\n"
                  f"The recorder's firmware can use a later version (v{maxVersion}). Some newer configuration\n"
                  "options in the dialog may be lost if the older version is used.\n\n"
                  "'Yes' will save using the newer version (recommended).\n"
                  "'No' will save using the file's original version."
                                  "Apply Configuration",
                                  wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
                                  self)
                if q == wx.YES:
                    version = maxVersion
            else:
                version = maxVersion
        self.updateDeviceConfig()
        self.device.config.applyConfig(unknown=True, version=version)


    def configChanged(self):
        """ Check if the configuration data has been changed.
        """
        self.updateConfigData()

        oldKeys = sorted(self.origConfigData.keys())
        newKeys = sorted(self.configData.keys())

        if oldKeys != newKeys:
            return True

        # Chew through the dictionaries manually, to handle items that are the
        # same but have different data types (e.g. `True` and ``1``).
        for k in newKeys:
            if self.configData.get(k) != self.origConfigData.get(k):
                return True

        return False


    def updateDisabledItems(self):
        """ Enable or disable config items according to their `disableIf`
            expressions and/or their parent group/tab's check or enabled state.
        """
        for item in self.configItems.values():
            item.updateDisabled()


    def _setClock(self):
        """ Set the recorder's clock, if selected. Wraps `device.setTime()`
            and provides an error dialog box.
        """
        if self.setClockCheck.IsEnabled() and self.setClockCheck.GetValue():
            logger.info("Setting clock...")
            try:
                if self.wifiTab is not None:
                    #  Stop the scan thread first to avoid conflicts
                    self.wifiTab.shutdown()
                self.device.setTime()
            except Exception as err:
                logger.error(f"Error setting clock: {err!r}")
                self.showError("The recorder's clock could not be set.",
                               "Configure Device",
                               style=wx.OK | wx.OK_DEFAULT | wx.ICON_WARNING)


    def _saveTabs(self):
        """ Call each tab's `save()` method, if necessary.
        """
        for tab in self.tabs:
            if not isinstance(tab, wifi_tab.WiFiSelectionTab):
                if tab.save() is False:
                    return
            elif (self.applyWifiChangesCheck is not None and
                  self.applyWifiChangesCheck.GetValue()):
                tab.save()


    # ===========================================================================
    #
    # ===========================================================================


    def OnImportButton(self, _evt: Optional[wx.Event]):
        """ Handle the "Import..." button.
        """
        wildcard = "Exported configuration data (*.xcg)|*.xcg"

        with wx.FileDialog(self, message="Export Device Configuration",
                           style=wx.FD_OPEN, wildcard=wildcard) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                configio.importConfig(self.device, dlg.GetPath())
                self.loadConfigData()


    def OnExportButton(self, _evt: Optional[wx.Event]):
        """ Handle the "Export..." button.
        """
        wildcard = "Exported configuration data (*.xcg)|*.xcg"
        if self.device.serial:
            defaultFile = "{}_config.xcg".format(self.device.serial)
        else:
            defaultFile = "config.xcg"

        with wx.FileDialog(self, message="Export Device Configuration",
                           defaultFile=defaultFile, wildcard=wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                try:
                    self.updateConfigData()
                    self.updateDeviceConfig()
                    configio.exportConfig(self.device, dlg.GetPath())

                except Exception as err:
                    # TODO: More specific error message
                    logger.error('Could not export configuration ({}: {})'
                                 .format(type(err).__name__, err))
                    self.showError(
                            "The configuration data could not be exported to the "
                            "specified file.", "Config Export Failed",
                            style=wx.OK | wx.ICON_EXCLAMATION)


    # ===========================================================================
    #
    # ===========================================================================


    def OnOK(self, evt: wx.Event):
        """ Handle dialog OK, saving changes.
        """
        if 0x18ff7f in self.device.config.items:
            wifiWasEnabled = bool(self.device.config.items[0x18ff7f].value)
        else:
            wifiWasEnabled = False

        if not self.saveOnOk:
            self.updateConfigData()
            evt.Skip()
            return

        try:
            self.saveConfigData()

        except (IOError, WindowsError) as err:
            if self.DEBUG and not isCompiled():
                raise

            msg = ("An error occurred when trying to update the recorder's "
                   "configuration data.\n\n")
            if err.errno == errno.ENOENT:
                msg += "The recorder appears to have been removed"
            else:
                msg += os.strerror(err.errno)

            if self.showAdvanced:
                if err.errno in errno.errorcode:
                    msg += " ({})".format(errno.errorcode[err.errno])
                else:
                    msg += " (error code {})".format(err.errno)

            self.showError(msg, "Configuration Error")
            evt.Skip()
            return

        except Exception as err:
            if self.DEBUG and not isCompiled():
                raise

            msg = ("An unexpected {} occurred when trying to update the "
                   "recorder's configuration data.\n\n".format(type(err).__name__))
            if self.showAdvanced:
                msg += str(err).capitalize()

            self.showError(msg, "Configuration Error")
            evt.Skip()
            return

        # Handle other exceptions here if need be.

        self._saveTabs()
        self._setClock()

        if self.device.hasWifi and self.configData.get(0x18ff7f) != wifiWasEnabled:
            q = wx.MessageBox("Reset recording device?\n\n"
                              "Enabling or disabling Wi-Fi requires the "
                              "recording device to reset in order to take effect.\n"
                              "Reset recorder now?",
                              "Configure Device",
                              style=(wx.YES_NO | wx.YES_DEFAULT
                                      | wx.ICON_QUESTION))
            if q == wx.YES:
                # FUTURE: This may need a callback to prevent the GUI from
                # getting flagged 'not responding.'
                self.device.command.reset()

        evt.Skip()


    def OnCancel(self, evt: wx.Event):
        """ Handle dialog cancel, prompting the user to save any changes.
        """
        if self.configChanged():
            q = self.showError("Save configuration changes before exiting?",
                               "Configure Device",
                               style=(wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT
                                      | wx.ICON_QUESTION))
            if q == wx.CANCEL:
                return
            elif q == wx.YES:
                self.saveConfigData()
                evt.Skip()
                return

        # If cancelled, the returned configuration data is `None`
        self.configData = None
        evt.Skip()


    def showError(self,
                  msg: str,
                  caption: str,
                  style: int = wx.OK | wx.OK_DEFAULT | wx.ICON_ERROR,
                  err: Optional[Exception] = None):
        """ Show an error message. Wraps the standard message box to add some
            debugging stuff.
        """
        if not msg.endswith(('.', '!', '?')):
            msg += "."

        q = wx.MessageBox(msg, caption, style=style, parent=self)
        if wx.GetKeyState(wx.WXK_CONTROL) and wx.GetKeyState(wx.WXK_SHIFT):
            raise
        if err is not None:
            logger.debug("%s: %r" % (msg, err))
        return q


# ===============================================================================
#
# ===============================================================================

def configureRecorder(path: Union[str, endaq.device.Recorder],
                      setTime: bool = True,
                      useUtc: bool = True,
                      parent: Optional[wx.Window] = None,
                      saveOnOk: bool = True,
                      showAdvanced: bool = False,
                      icon: Optional[wx.Icon] = None,
                      exceptions: bool = True,
                      debug: bool = __DEBUG__) -> Union[tuple, None]:
    """ Create the configuration dialog for a recording device.

        :param path: The path to the data recorder (e.g. a mount point under
            *NIX or a drive letter under Windows)
        :param setTime: If `True`, the checkbox to set the device's clock
            on save will be checked by default.
        :param useUtc: If `True`, the 'in UTC' checkbox for wake times will
            be checked by default.
        :param parent: The parent window, or `None`.
        :param saveOnOk: If `False`, exiting the dialog with OK will not save
            to the recorder. Primarily for debugging.
        :param showAdvanced: If `True`, show configuration options flagged
            as 'advanced.'
        :param icon: An icon to appear in the window's titlebar (not
            visible in all operating systems/window managers).
        :param exceptions: If `True`, allow all exceptions to be raised. If
            `False`, show descriptive message boxes when anticipated errors
             occur, intended for standalong use.
        :param debug: If `True`, show/log debugging messages.
        :return: `None` if configuration was cancelled, else a tuple
            containing:
                * The data written to the recorder (a nested dictionary)
                * Whether `setTime` was checked before save
                * Whether `useUTC` was checked before save
                * The configured device itself
                * The post-configuration message (could be `None`)
    """
    if isinstance(path, endaq.device.Recorder):
        dev = path
        path = dev.path
    else:
        dev = endaq.device.getRecorder(path)

    if not dev:
        msg = "Path '{}' does not appear to be a recorder".format(path)
        if exceptions:
            raise ValueError(msg)

        wx.MessageBox(msg, "Configuration Error",
                      parent=parent,
                      style=wx.OK | wx.OK_DEFAULT | wx.ICON_ERROR)
        return None

    if not dev.config.getConfigUI():
        if exceptions:
            raise endaq.device.DeviceError("The device appears to have corrupted configuration UI data.", dev)

        wx.MessageBox("Could not configure recorder\n\n"
                      "Valid configuration UI data could not be retrieved for the device.",
                      "Configuration Error",
                      parent=parent,
                      style=wx.OK | wx.OK_DEFAULT | wx.ICON_ERROR)
        return None

    try:
        with ConfigDialog(parent, device=dev, setTime=setTime,
                          useUtc=useUtc, saveOnOk=saveOnOk,
                          showAdvanced=showAdvanced,
                          icon=icon, debug=debug) as dlg:
            dlg.ShowModal()
            result = dlg.configData
            setTime = dlg.setClockCheck.GetValue()
            useUtc = dlg.useUtc
            msg = dlg.postConfigMessage or getattr(dev, "POST_CONFIG_MSG", None)

    except PermissionError:
        if exceptions:
            raise

        wx.MessageBox("Another process appears to have control of the device.\n\n"
                      "Close other application that could be using the recorder and try again.",
                      "Configuration Error",
                      parent=parent,
                      style=wx.OK | wx.OK_DEFAULT | wx.ICON_ERROR)
        return None

    if result is None:
        return None

    return result, setTime, useUtc, dev, msg
