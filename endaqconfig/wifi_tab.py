"""
Tab for configuring Wi-Fi.

Created on Nov 13, 2019

:author: dstokes
"""
import threading
from time import time, sleep

import wx
from wx.lib.newevent import NewEvent
import wx.lib.sized_controls as SC
import wx.lib.mixins.listctrl as listmix

from .base import Tab
from .base import logger, registerTab
from .widgets import icons

from endaq.device import DeviceError, DeviceTimeout
from endaq.device.response_codes import DeviceStatusCode


# ===============================================================================
#
# ===============================================================================

AUTH_TYPES = ("None", "WPA", "WPA2", "Unknown")
DEFAULT_AUTH = 1

CONNECTION_STATUS_TO_STR = {
    0: "",
    1: "Trying to connect",
    2: "Connected",
}

# ===============================================================================
#
# ===============================================================================

# Response to the Wi-Fi list being read from the device. It might take a little
# time, so it will be done asynchronously. Event attributes:
# * data: List of AP info dictionaries.
# * error: None if no error occurred, or the instance of the Exception if one did
EvtConfigWiFiScan, EVT_CONFIG_WIFI_SCAN = NewEvent()

# An event to be used when the Wi-Fi connection has been just been checked
# * result: The result of the Wi-Fi connection check (in the form exported by the setWifi method)
EvtConfigWiFiConnectionCheck, EVT_CONFIG_WIFI_CONNECTION_CHECK = NewEvent()

# A custom event to be called when the Wi-Fi tab is closed
EvtClosingTemp, EVT_CLOSING_TEMP = NewEvent()


class WiFiScanThread(threading.Thread):
    """ Thread for asynchronously retrieving a list of Wi-Fi APs from the
        wireless-enabled device. Posts an `EVT_CONFIG_WIFI_SCAN` event when
        complete. Can be cancelled by calling `cancel.set()`.
    """


    def __init__(self, parent, interval=.25, timeout=10, pause=0):
        """ Constructor.

            :param parent: The parent `WifiSelectionTab`
            :keyword interval: Time (in seconds) between reads of the device's
                RESPONSE file.
            :keyword timeout: Time (in seconds) to wait for the device to
                complete a Wi-Fi scan.
            :keyword pause: A time (in seconds) to delay before the scan.
        """
        super(WiFiScanThread, self).__init__(name=type(self).__name__)
        self.daemon = True

        self.parent = parent
        self.interval = interval
        self.timeout = timeout
        self.pause = pause
        self.cancel = threading.Event()
        self.cancel.clear()


    def run(self):
        """ The scanning thread's main loop.
        """
        data = None
        E = None

        sleep(self.pause)

        try:
            data = self.parent.device.command.scanWifi(timeout=self.timeout,
                                                       interval=self.interval,
                                                       callback=self.cancel.is_set)
        except Exception as err:
            E = err

        evt = EvtConfigWiFiScan(data=data, error=E)

        try:
            wx.PostEvent(self.parent, evt)
        except RuntimeError:
            # Dialog probably closed during scan, which is okay.
            pass


class ContinousNetworkStatusChecker(threading.Thread):
    """ Thread for continually checking the current status of the network
        connection, done asynchronously.
    """

    def __init__(self, parent, interval=4, timeout=10):
        """ Constructor.

            :param parent: The parent `WifiSelectionTab`
            :param interval: Time (in seconds) between each check of the network status
            :param timeout: Time (in seconds) to wait for the device to finish checking the network status
        """
        super(ContinousNetworkStatusChecker, self).__init__(name=type(self).__name__)
        self.daemon = True

        self.parent = parent
        self.interval = interval
        self.timeout = timeout
        self.cancel = threading.Event()
        self.cancel.clear()


    def run(self):
        """ The main loop.
        """
        sleep(self.interval)
        while bool(self.parent) and not self.cancel.is_set():
            start_time = time()
            try:
                result = self.parent.device.command.queryWifi(timeout=5)
                evt = EvtConfigWiFiConnectionCheck(result=result)
                if bool(self.parent):
                    wx.PostEvent(self.parent, evt)

            except DeviceTimeout:
                logger.warning("Timed out when checking the network connection, retrying")

            except DeviceError as E:
                if E.args and E.args[0] == DeviceStatusCode.ERR_BUSY:
                    logger.info("Device repoted ERR_BUSY, retrying")
                else:
                    logger.error(E)
                    raise

            except IOError as E:
                logger.warning(E)

                evt = EvtClosingTemp()  # wx.CloseEvent(id=-1)
                if bool(self.parent):
                    wx.PostEvent(self.parent, evt)

                return

            to_sleep = max(0, self.interval - (time() - start_time))
            sleep(to_sleep)


# ===============================================================================
#
# ===============================================================================

class AddWifiDialog(SC.SizedDialog):
    """ Simple dialog for entering data to connect to a hidden (or out-of-range)
        network.
    """


    def __init__(self, parent, wxId=-1, title="Add Access Point",
                 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                 booleanAuth=True, authType=DEFAULT_AUTH, **kwargs):
        """ Constructor. Takes standard dialog arguments, plus:

            :keyword booleanAuth: If `True`, the specific type of authorization
                isn't selectable, just its presence or absence. For future use.
            :keyword authType: The default authorization type number. Will
                be a preference or the last value used, read from the
        """
        self.booleanAuth = booleanAuth
        super(AddWifiDialog, self).__init__(parent, wxId, title=title,
                                            style=style, **kwargs)

        pane = self.GetContentsPane()
        pane.SetSizerType("form")

        wx.StaticText(pane, -1, "SSID (Name):").SetSizerProps(valign='center')
        self.ssidField = wx.TextCtrl(pane, -1, "")
        self.ssidField.SetSizerProps(expand=True, valign='center')

        wx.StaticText(pane, -1, "Security:").SetSizerProps(valign='center')
        if booleanAuth:
            self.authField = wx.CheckBox(pane, -1, "Password Required")
            self.authField.SetValue(bool(authType))
            pwFieldEnabled = self.authField.GetValue()
            self.Bind(wx.EVT_CHECKBOX, self.OnAuthCheck)
        else:
            self.authField = wx.Choice(pane, -1, choices=AUTH_TYPES)
            self.authField.SetSelection(authType)
            pwFieldEnabled = self.authField.GetSelection() != 0
            self.Bind(wx.EVT_CHOICE, self.OnAuthChoice)
        self.authField.SetSizerProps(expand=True, valign='center')

        wx.StaticText(pane, -1, "Password:").SetSizerProps(valign='center')
        self.pwField = wx.TextCtrl(pane, -1, "", style=wx.TE_PASSWORD)
        self.pwField.SetSizerProps(expand=True, valign='center')
        self.pwField.Enable(pwFieldEnabled)

        # add dialog buttons
        self.SetButtonSizer(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL))

        # a little trick to make sure that you can't resize the dialog to
        # less screen space than the controls need
        self.Fit()
        size = self.GetSize() + wx.Size(60, 0)
        self.SetSize(size)
        self.SetMinSize(size)
        self.ssidField.SetFocus()


    def OnAuthChoice(self, evt):
        """ Handle authorization selection from the drop-down list, if
            not `booleanAuth`.
        """
        self.pwField.Enable(self.authField.GetSelection() != 0)
        evt.Skip()


    def OnAuthCheck(self, evt):
        """ Handle authorization selection checkbox, if `booleanAuth`.
        """
        self.pwField.Enable(self.authField.GetValue())


    def getValue(self):
        """ Retrieve the dialog's data.

            :return: A dictionary of Wi-Fi AP info and the password
        """
        if self.booleanAuth:
            auth = self.authField.GetValue()
        else:
            auth = AUTH_TYPES[self.authField.GetSelection()]

        result = {'SSID': self.ssidField.GetValue(),
                  'RSSI': None,
                  'AuthType': auth,
                  'Known': False,
                  'Selected': False}

        return result, self.pwField.GetValue()


# ===============================================================================
#
# ===============================================================================

@registerTab
class WiFiSelectionTab(Tab):
    """ Tab for selecting the wireless access point for a W-series recorder.
        This communicates directly with the device to get the visible
        networks and to save passwords.
    """
    COLUMNS = ("Wi-Fi Network", "Security", "Connected")

    # 'Constant' value for the label, read from CONFIG_UI for 'normal' tabs
    label = "Wi-Fi"

    # FUTURE: Once multiple saved passwords is a thing, this will be provided
    # in the CONFIG_UI data.
    storeMultiplePasswords = False

    # FUTURE: Current HW only specifies authentication's presence or absence.
    # Future hardware might now. Will eventually be in CONFIG_UI data
    booleanAuth = True

    class WifiListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
        # Required to create an auto-resizing list
        def __init__(self, parent, ID, pos=wx.DefaultPosition,
                     size=wx.DefaultSize, style=0):
            wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
            listmix.ListCtrlAutoWidthMixin.__init__(self)


    def __init__(self, *args, **kwargs):
        """ Constructor. Will probably be completely replaced once this is
            integrated with the rest of the tabs.
        """
        self.info = []
        self.parent = kwargs['root']
        self.device = kwargs['root'].device

        super(WiFiSelectionTab, self).__init__(*args, **kwargs)

        self.networkStatusThread = ContinousNetworkStatusChecker(self)
        self.networkStatusThread.start()


    def loadImages(self):
        """ Load the Wi-Fi signal strength/security icons.
        """
        self.il = wx.ImageList(20, 16, mask=True)
        self.icons = [self.il.Add(f.GetBitmap()) for f in icons.WIFI_ICONS]


    def initUI(self):
        """ Build the user interface, populating the Tab.
            Separated from `__init__()` for the sake of subclassing.
        """
        self.scanThread = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.loadImages()

        # Set up the AP list
        self.list = self.WifiListCtrl(self, -1,
                                      style=(wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SORT_ASCENDING |
                                             wx.LC_VRULES | wx.LC_HRULES | wx.LC_SINGLE_SEL))
        # self.list.EnableCheckBoxes()
        sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)

        self.list.setResizeColumn(0)
        self.list.SetImageList(self.il, wx.IMAGE_LIST_SMALL)
        info = wx.ListItem()
        info.SetMask(wx.LIST_MASK_TEXT | wx.LIST_MASK_IMAGE | wx.LIST_MASK_FORMAT)
        info.SetImage(-1)
        info.SetAlign(0)
        info.SetText(self.COLUMNS[0])
        self.list.InsertColumn(0, info)
        self.list.SetColumnWidth(0, wx.LIST_AUTOSIZE)

        self.list.InsertColumn(1, self.COLUMNS[1], width=wx.LIST_AUTOSIZE)
        self.list.InsertColumn(2, self.COLUMNS[2], width=wx.LIST_AUTOSIZE)

        self.listFont = self.list.GetFont()
        self.boldFont = self.listFont.Bold()
        self.italicFont = self.listFont.Italic()
        self.struckFont = self.listFont.Strikethrough()
        #         self.notFoundColor = wx.Colour(127,127,127)

        # Rescan button (and footnote text)
        scansizer = wx.BoxSizer(wx.HORIZONTAL)
        self.addButton = wx.Button(self, -1, "Add...")
        self.rescan = wx.Button(self, -1, "Rescan")

        scansizer.Add(self.addButton, 0, wx.EAST | wx.SHAPED, 8)

        scansizer.AddStretchSpacer()

        scansizer.Add(self.rescan, 0, wx.EAST | wx.SHAPED, 8)

        sizer.Add(scansizer, 0, wx.EXPAND | wx.EAST)

        # Password field components
        pwsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pwCheck = wx.CheckBox(self, -1, "Change Password to Selected AP:")
        self.pwCheck.Enable(False)
        self.pwField = wx.TextCtrl(self, -1, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
        self.pwField.Enable(False)

        pwstyle = wx.RESERVE_SPACE_EVEN_IF_HIDDEN
        pwsizer.AddMany(((self.pwCheck, 0, pwstyle | wx.ALIGN_CENTER_VERTICAL),
                         (self.pwField, 1, pwstyle | wx.EXPAND)))
        sizer.Add(pwsizer, 0, wx.EXPAND | wx.ALL, 8)

        # For future use
        self.forgetCheck = wx.CheckBox(self, -1, "Forget this AP on exit")
        sizer.Add(self.forgetCheck, 0, wx.EXPAND | wx.WEST | wx.SOUTH, 8)

        self.currentConnectionLabel = wx.StaticText(self, -1, "")
        self.applyButton = wx.Button(self, -1, "Apply Wi-Fi Changes")

        connection_and_apply_sizer = wx.BoxSizer(wx.HORIZONTAL)
        connection_and_apply_sizer.AddMany(
                ((self.currentConnectionLabel, 1, wx.EXPAND | wx.ALL, 8),
                 (self.applyButton, 0, wx.SOUTH | wx.EAST, 8)))

        sizer.Add(connection_and_apply_sizer, 0, wx.EXPAND)

        self.SetSizer(sizer)

        # For doing per-item tool tips in the list
        self.listToolTips = []
        self.lastToolTipItem = -1

        self.selected = -1
        self.firstSelected = -1
        self.lastSelected = -1
        self.deleted = []
        self.passwords = {}

        self.list.Bind(wx.EVT_MOTION, self.OnListMouseMotion)
        self.rescan.Bind(wx.EVT_BUTTON, self.OnRescan)
        self.addButton.Bind(wx.EVT_BUTTON, self.OnAddButton)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self.list)
        self.pwCheck.Bind(wx.EVT_CHECKBOX, self.OnPasswordChecked)
        self.pwField.Bind(wx.EVT_SET_FOCUS, self.OnPasswordFocus)
        self.pwField.Bind(wx.EVT_TEXT_ENTER, self.OnApplyButton)
        self.pwField.Bind(wx.EVT_TEXT, self.OnPasswordText)
        self.applyButton.Bind(wx.EVT_BUTTON, self.OnApplyButton)

        # FUTURE: For use with multiple AP memory
        if self.booleanAuth:
            self.forgetCheck.Hide()
        else:
            self.forgetCheck.Bind(wx.EVT_CHECKBOX, self.OnForgetChecked)
            self.list.Bind(wx.EVT_COMMAND_RIGHT_CLICK, self.OnListRightClick)
            self.list.Bind(wx.EVT_RIGHT_UP, self.OnListRightClick)  # GTK

        self.Bind(EVT_CONFIG_WIFI_SCAN, self.OnWiFiScan)
        self.Bind(EVT_CONFIG_WIFI_CONNECTION_CHECK, self.OnConnectionCheck)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(EVT_CLOSING_TEMP, self.OnClose)

        self.getInfo()


    def OnConnectionCheck(self, evt):
        result = evt.result

        text_to_display = CONNECTION_STATUS_TO_STR[result['WiFiConnectionStatus']]
        is_connected = result['WiFiConnectionStatus'] == 2

        for j in range(self.list.GetItemCount()):
            label = u'\u2713' if is_connected and self.list.GetItemText(j, col=0) == result['SSID'] else '-'

            self.list.SetItem(j, column=2, label=label)

        self.currentConnectionLabel.SetLabel(text_to_display)  # I'm not sure if this is doing anything


    def makeToolTip(self, ap):
        """ Generate the tool tip string for an AP. Isolated because it's
            bulky.
        """
        ssid = ap['SSID']
        strength = ap['RSSI']
        security = ap['AuthType']
        known = ap['Known']
        selected = ap['Selected']

        # if strength < 0:
        if strength is None or strength >= 0:  # Don't think the second condition is needed anymore
            tooltip = u"%s (not in range)" % ssid
        else:
            tooltip = u"%s (signal strength: %d%%)" % (ssid, 100 - abs(strength))

        if selected:
            if security:
                tooltip += u"\nSaved password, currently configured."
            else:
                tooltip += u"\nCurrently configured."
        # FUTURE: For use with multiple AP memory
        elif ssid in self.deleted:
            tooltip += u"\nWill be forgotten."
        elif security and not known:
            # AP not previously configured; mark it.
            tooltip += u"\nRequires password."
        elif security:
            tooltip += u"\nPassword saved."

        return tooltip


    def makeAuthTypeString(self, ap):
        """ Turn the AP AuthType into a string.
        """
        # Currently, AuthType is boolean (any or none), but might eventually
        # be an index.
        if self.booleanAuth:
            if ap['AuthType']:
                return u"\u2713"
            else:
                return "-"
        else:
            return AUTH_TYPES[ap['AuthType']]


    def getInfo(self):
        """ Get Wi-Fi information from the device. Starts the asynchronous
            device-reading thread.
        """
        if self.scanThread and self.scanThread.is_alive():
            return

        self.list.Enable(False)
        self.addButton.Enable(False)
        self.pwCheck.Enable(False)
        self.pwField.Enable(False)
        self.forgetCheck.Enable(False)
        self.rescan.SetLabelText("Scanning...")
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        self.scanThread = WiFiScanThread(self)
        self.scanThread.start()


    def populate(self):
        """ Fill out the AP list. Called when the Wi-Fi scan thread finishes.
        """
        self.firstSelected = -1
        self.lastSelected = -2
        self.listToolTips = []

        self.forgetCheck.Enable(False)

        self.list.DeleteAllItems()

        for n, ap in enumerate(self.info):
            ssid = ap['SSID']
            strength = ap['RSSI']
            security = ap['AuthType']
            selected = ap['Selected']

            if strength is None:
                icon = 11 if security else 5

                # arbitrarily high since I can't use infinity and numpy isn't imported for using finfo
                strength = 1e6
            else:
                # TODO: Use some sort of curve to round up low values.
                if strength >= 0:
                    icon = 5
                elif strength >= .1:
                    icon = 0
                else:
                    # The min is done for the case where strength is
                    # exactly -100 max (and didn't think too hard about it)
                    icon_index = 4 + min(0, int(strength / 25))
                    icon = max(1, self.icons[icon_index])

                if security:
                    icon += 6

            idx = self.list.InsertItem(- strength, ssid, icon)
            self.list.SetItem(idx, 1, self.makeAuthTypeString(ap))
            self.list.SetItemData(idx, n)
            item = self.list.GetItem(idx)

            ap['idx'] = idx

            if selected:
                # Indicate that this is the previously selected AP
                if self.selected == -1:
                    self.selected = n

                self.firstSelected = n

                item.SetText(item.GetText() + " *")

            elif ssid in self.deleted:
                item.SetFont(self.struckFont)

            #             if strength < 0:
            #                 item.SetTextColour(self.notFoundColor)

            self.list.SetItem(item)
            self.listToolTips.append(self.makeToolTip(ap))

        # If the selected index is greater than the number of options, reset it to -1.
        # (This is used to avoid several bugs)
        # if self.selected > len(self.info) - 1:

        # This is always done now to avoid default selections being set as the Wi-Fi.
        self.selected = -1

        # if len(self.info) != 0:
        #     self.list.Select(self.info[self.selected]['idx'])

        self.list.SortItems(lambda a, b: 2 * int(a > b) - 1)

        self.updateApplyButton()


    def updateApplyButton(self):
        """ Enable or disable the "Apply" button if any changes have been
            made.
        """
        enable = False

        # Check for changes of selected AP
        if self.selected != self.firstSelected:
            enable = True
        elif self.info[self.firstSelected]['SSID'] in self.passwords:
            enable = True

        # FUTURE: Do checks to other APs for multiple AP configuration

        try:
            self.applyButton.Enable(enable)
        except RuntimeError:
            # Dialog closed?
            pass

        return enable


    def shutdown(self):
        """ Kill the Wi-Fi scanning and status threads.
        """
        try:
            logger.debug('Shutting down Wi-Fi scan and status threads')
            self.scanThread.cancel.set()
            self.networkStatusThread.cancel.set()
            while ((self.scanThread and self.scanThread.is_alive()) or
                   (self.networkStatusThread and self.networkStatusThread.is_alive())):
                pass
        except AttributeError:
            # Can sometimes occur in race conditions during shutdown.
            pass


    # ===========================================================================
    #
    # ===========================================================================


    def OnRescan(self, evt):
        """ Handle "Rescan" button press.
        """
        self.getInfo()


    def OnWiFiScan(self, evt):
        """ Handle the asynchronous Wi-Fi scan finishing.
        """
        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))

        if evt.error is not None:  # Scan encountered error; show warning.

            if isinstance(evt.error, IOError):
                return
            elif isinstance(evt.error, DeviceTimeout):
                err_message = "Timed out when attempting to scan Wi-Fi."
            else:
                err_message = ("An unexpected %s occurred when attempting "
                               "to scan for Wi-Fi networks." % type(evt.error).__name__)

            wx.MessageBox(message=err_message, caption="Wi-Fi Scan Error",
                          style=wx.OK, parent=self)

        self.list.Enable()
        self.addButton.Enable()
        self.pwCheck.Enable()
        self.pwField.Enable()
        self.rescan.SetLabelText("Rescan")

        if evt.error is not None:
            if not isinstance(evt.error, DeviceTimeout):
                raise evt.error
        else:
            self.info = evt.data

            self.populate()


    def OnAddButton(self, evt):
        """ Handle 'Add' button press.
        """
        dlg = AddWifiDialog(self, -1, booleanAuth=self.booleanAuth)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return

        newap, pw = dlg.getValue()
        dlg.Destroy()

        if not self.storeMultiplePasswords:
            self.passwords.clear()
        self.passwords[newap['SSID']] = pw

        for ap in self.info[:]:
            if ap['SSID'] == newap['SSID']:
                self.info.remove(ap)

        self.info.append(newap)
        self.selected = len(self.info) - 1
        self.populate()


    def OnItemSelected(self, evt):
        """ Handle an AP list item getting selected.
        """
        item = evt.GetItem()
        item.SetFont(self.boldFont)
        self.list.SetItem(item)
        self.selected = item.GetData()
        ap = self.info[self.selected]

        changedPw = ap['SSID'] in self.passwords

        if ap['Known']:
            self.pwCheck.SetLabelText("Change Password to Selected AP:")
        else:
            self.pwCheck.SetLabelText("Set Password to Selected AP:")

        self.pwCheck.SetValue(changedPw)
        self.forgetCheck.Enable(ap['Known'])

        self.forgetCheck.SetValue(ap['SSID'] in self.deleted)

        hasPw = bool(ap['AuthType'])
        self.pwCheck.Enable(hasPw)
        self.pwField.Enable(hasPw)
        self.pwField.SetValue(self.passwords.get(ap['SSID'], ""))

        # self.selectedLabel.Enable(ap['Selected'])
        self.updateApplyButton()


    def OnItemDeselected(self, evt):
        """ Handle an AP list item getting deselected.
        """
        # self.selectedLabel.Enable(False)
        item = evt.GetItem()
        item.SetFont(self.listFont)
        self.list.SetItem(item)
        self.selected = -1


    def OnForgetChecked(self, evt):
        """ Handle the 'Forget' checkbox changing.
            For future use, when multiple passwords are stored.
        """
        ssid = self.info[self.selected]['SSID']
        self.deleted.remove(ssid)

        if self.forgetCheck.GetValue():
            self.deleted.append(ssid)

        self.populate()


    def OnPasswordChecked(self, evt):
        """ Handle the 'Set/Change Password' checkbox changing.
        """
        if not self.pwCheck.GetValue():
            self.passwords.pop(self.info[self.selected]['SSID'], None)
            self.pwField.SetValue('')
        self.updateApplyButton()


    def OnPasswordFocus(self, evt):
        """ Handle the password field being clicked in.
        """
        # Erase the field unless the user hasn't changed selected AP
        if self.selected != self.lastSelected:
            self.pwField.SetValue('')
            self.lastSelected = self.selected

        evt.Skip()


    def OnPasswordText(self, evt):
        """ Handle typing in the password field.
        """
        ssid = self.info[self.selected]['SSID']
        text = evt.GetString()
        if text:
            self.pwCheck.SetValue(True)
            if not self.storeMultiplePasswords:
                self.passwords.clear()
            self.passwords[ssid] = evt.GetString()
            self.updateApplyButton()
        evt.Skip()


    def OnListMouseMotion(self, evt):
        """ Handle mouse movement, updating the tool tips, etc.
        """
        # This determines the list item under the mouse and shows the
        # appropriate tool tip, if any.
        index, _ = self.list.HitTest(evt.GetPosition())
        if index != -1 and index != self.lastToolTipItem:
            try:
                item = self.list.GetItemData(index)
                if self.listToolTips[item] is not None:
                    self.list.SetToolTip(self.listToolTips[item])
                else:
                    self.list.UnsetToolTip()
            except IndexError:
                pass
            self.lastToolTipItem = index
        evt.Skip()


    def OnListRightClick(self, evt):
        """ Handle a list item being right-clicked.
            For future use.
        """
        selected = self.info[self.selected]

        menu = wx.Menu()
        mi = menu.Append(wx.ID_DELETE, 'Forget "%s"' % selected['SSID'])
        self.Bind(wx.EVT_MENU, self.OnDelete, id=wx.ID_DELETE)

        if not (selected['Known'] and selected['RSSI'] < 0):
            mi.Enable(False)

        self.PopupMenu(menu)
        menu.Destroy()


    def OnDelete(self, evt):
        """ Delete (forget) a saved AP.
            For future use (current HW doesn't keep multiple APs).
        """
        self.deleted.append(self.info[self.selected]['SSID'])
        self.populate()


    def OnClose(self, evt):
        """ Handle dialog closed.
        """
        self.shutdown()
        self.parent.Close()
        evt.Skip()


    def OnApplyButton(self, evt):
        """ Saves the current information, then does a new Wi-Fi scan.
        """
        self.save()
        # I removed this functionality given we now check for connection information periodically
        # self.getInfo()


    # ===========================================================================
    #
    # ===========================================================================


    def save(self):
        """ Save Wi-Fi configuration data to the device.
        """
        data = []

        # `updateApplyButton()` also returns whether changes have been made.
        if self.updateApplyButton():
            for n, ap in enumerate(self.info):
                ssid = ap['SSID']
                if ssid in self.deleted:
                    continue

                isSelected = int(n == self.selected)
                d = {'SSID': ssid,
                     'Selected': isSelected}

                # This uses the password supplied in the 'change password' section
                if ssid in self.passwords:
                    d['Password'] = self.passwords[ssid]
                elif isSelected and ap['Selected']:
                    break

                if self.storeMultiplePasswords or isSelected:
                    data.append(d)

        # FUTURE: Any SSIDs in self.deleted should be deleted here.

        try:
            self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
            self.applyButton.Enable(False)
            self.device.command.setWifi(data)
        except IOError:
            logger.warning("An IOError occured while setting the Wi-Fi. "
                           "This is usually because the device was unplugged part of the way through")
        except DeviceTimeout:
            wx.MessageBox(
                    message="Timed out when attempting to set device Wi-Fi (communicating with device). Wi-Fi was not set.",
                    caption="Wi-Fi Configuration Error",
                    style=wx.OK,
                    parent=self)
            return False
        except Exception as E:
            wx.MessageBox(
                    "An unexpected %s occurred when attempting to set the Wi-Fi network." % type(E).__name__,
                    caption="Wi-Fi Configuration Error",
                    style=wx.OK | wx.ICON_ERROR,
                    parent=self)
            return False
        finally:
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            self.updateApplyButton()

        return True
