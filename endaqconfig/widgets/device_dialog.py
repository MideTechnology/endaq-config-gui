"""
Dialog for selecting recording devices.

"""

from collections import namedtuple
from datetime import datetime
import time

import wx
import wx.lib.sized_controls as sc
import wx.lib.mixins.listctrl as listmix

from endaq.device import getDevices, getDeviceList, RECORDERS
from endaq.device import deviceChanged

from . import icons

#===============================================================================
#
#===============================================================================


class DeviceSelectionDialog(sc.SizedDialog, listmix.ColumnSorterMixin):
    """ The dialog for selecting data to export.
    """

    ID_SET_TIME = wx.NewIdRef()
    ID_START_RECORDING = wx.NewIdRef()

    # Indices of icons. Proportional to severity.
    ICON_NONE, ICON_INFO, ICON_WARN, ICON_ERROR = range(4)

    # Named tuple to make handling columns slightly cleaner (names vs. indices).
    ColumnInfo = namedtuple("ColumnInfo", ['name',       # Column header text
                                           'propName',   # Name of object property
                                           'formatter',  # To-string function
                                           'default'])   # Default display string

    # The displayed columns
    COLUMNS = (ColumnInfo("Path", "path", str, ''),
               ColumnInfo("Name", "name", str, ''),
               ColumnInfo("Type", "productName", str, ''),
               ColumnInfo("Serial #", "serial", str, ''))

    ADVANCED_COLUMNS = (COLUMNS +
                        (ColumnInfo("HW Rev.", "hardwareVersion", str, ''),
                         ColumnInfo("FW Rev.", "firmware", str, '')))

    # Tool tips for the 'record' button
    RECORD_UNSELECTED = "No recorder selected"
    RECORD_UNSUPPORTED = "Device does not support recording via software"
    RECORD_ENABLED = "Initiate recording on the selected device"

    # ===============================================================================
    #
    # ===============================================================================

    class DeviceListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
        # Required to create a sortable list

        DEFAULT_STYLE = (wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SORT_ASCENDING
                         | wx.LC_VRULES | wx.LC_HRULES | wx.LC_SINGLE_SEL)

        def __init__(self, parent, ID, pos=wx.DefaultPosition,
                     size=wx.DefaultSize, style=DEFAULT_STYLE):
            wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
            listmix.ListCtrlAutoWidthMixin.__init__(self)

    # ===============================================================================
    #
    # ===============================================================================


    def GetListCtrl(self):
        # Required by ColumnSorterMixin
        return self.list


    def __init__(self, *args, **kwargs):
        """ Constructor. Takes standard dialog arguments, plus:

            :keyword root: The parent object (e.g. a viewer window).
            :keyword autoUpdate: The time between updates of the device list.
            :keyword types: A list of known recorder subclasses.
        """
        # Clear cached devices
        RECORDERS.clear()

        style = wx.DEFAULT_DIALOG_STYLE \
            | wx.RESIZE_BORDER \
            | wx.MAXIMIZE_BOX \
            | wx.MINIMIZE_BOX \
            | wx.DIALOG_EX_CONTEXTHELP \
            | wx.SYSTEM_MENU

        self.root = kwargs.pop('root', None)
        self.autoUpdate = kwargs.pop('autoUpdate', 500)
        self.hideClock = kwargs.pop('hideClock', False)
        self.hideRecord = kwargs.pop('hideRecord', False)
        self.showWarnings = kwargs.pop('showWarnings', True)
        self.showAdvanced = kwargs.pop('showAdvanced', False)
        okText = kwargs.pop('okText', "Configure")
        okHelp = kwargs.pop('okHelp', 'Configure the selected device')
        cancelText = kwargs.pop('cancelText', "Close")
        icon = kwargs.pop('icon', None)
        kwargs.setdefault('style', style)

        sc.SizedDialog.__init__(self, *args, **kwargs)

        if icon is not False:
            icon = icon or icons.icon.GetIcon()
            self.SetIcon(icon)

        if self.showAdvanced:
            self.COLUMNS = self.ADVANCED_COLUMNS

        self.recorders = {}
        self.recorderPaths = tuple(getDeviceList())
        self.selected = None
        self.selectedIdx = None
        self.firstDrawing = True

        # TODO: listWidth was supposed to be used for something, but it isn't.
        self.listWidth = 420

        pane = self.GetContentsPane()
        pane.SetSizerProps(expand=True)

        self.itemDataMap = {}  # required by ColumnSorterMixin

        self.list = self.DeviceListCtrl(pane, -1)

        images = wx.ImageList(16, 16)
        empty = wx.Bitmap(16, 16)
        empty.SetMaskColour(wx.BLACK)
        images.Add(empty)
        for i in (wx.ART_INFORMATION, wx.ART_WARNING, wx.ART_ERROR):
            images.Add(wx.ArtProvider.GetBitmap(i, wx.ART_CMN_DIALOG, (16, 16)))
        self.list.AssignImageList(images, wx.IMAGE_LIST_SMALL)

        self.list.SetSizerProps(expand=True, proportion=1)

        # Selected device info
        self.infoText = wx.StaticText(pane, -1, "")
        self.infoText.SetSizerProps(expand=True)

        buttonpane = sc.SizedPanel(pane, -1)
        buttonpane.SetSizerType("horizontal")
        buttonpane.SetSizerProps(expand=True)

        self.setClockButton = wx.Button(buttonpane, self.ID_SET_TIME,
                                        "Set All Clocks")
        self.setClockButton.SetSizerProps(halign="left")
        self.setClockButton.SetToolTip("Set the time of every attached "
                                       "recorder with a real-time clock")

        self.recordButton = wx.Button(buttonpane, self.ID_START_RECORDING,
                                      "Start Recording")
        self.recordButton.SetSizerProps(halign="left")
        self.recordButton.SetToolTip(self.RECORD_ENABLED)
        self.recordButton.Enable(False)

        sc.SizedPanel(buttonpane, -1).SetSizerProps(proportion=1)  # Spacer

        self.okButton = wx.Button(buttonpane, wx.ID_OK, okText)
        self.okButton.SetToolTip(okHelp)
        self.okButton.SetSizerProps(halign="right")
        self.okButton.Enable(False)
        self.cancelButton = wx.Button(buttonpane, wx.ID_CANCEL, cancelText)
        self.cancelButton.SetSizerProps(halign="right")

        # Call deviceChanged() to set the initial state. Result ignored.
        deviceChanged(recordersOnly=False, clear=True)
        self.populateList()
        listmix.ColumnSorterMixin.__init__(self, len(self.ColumnInfo._fields))

        self.Fit()
        self.SetSize((self.listWidth + (self.GetDialogBorder()*4), 300))
        self.SetMinSize((400, 300))
        self.SetMaxSize((1500, 600))

        self.Layout()
        self.Centre()

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self.list)
        self.list.Bind(wx.EVT_LEFT_DCLICK, self.OnItemDoubleClick)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self.list)
        self.Bind(wx.EVT_SHOW, self.OnShow)

        if self.hideClock:
            self.setClockButton.Hide()
        else:
            self.Bind(wx.EVT_BUTTON, self.setClocks, id=self.ID_SET_TIME)

        if self.hideRecord:
            self.recordButton.Hide()
        else:
            self.Bind(wx.EVT_BUTTON, self.startRecording, id=self.ID_START_RECORDING)

        if not self.showWarnings:
            self.infoText.Hide()

        # For doing per-item tool tips in the list
        self.lastToolTipItem = -1
        self.list.Bind(wx.EVT_MOTION, self.OnListMouseMotion)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.TimerHandler)


    def TimerHandler(self, _evt=None):
        """ Handle timer 'tick' by refreshing device list.
        """
        if deviceChanged(recordersOnly=False):
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROWWAIT))
            newPaths = tuple(getDeviceList())
            if newPaths == self.recorderPaths:
                self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
                return
            self.recorderPaths = newPaths
            self.populateList()
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    def setItemIcon(self, index, dev):
        """ Set the warning icon, message and tool tips for recorders with
            problems.
        """
        tips = []
        icon = self.ICON_NONE
        try:
            life = dev.getEstLife()
            calExp = dev.getCalExpiration()
            freeSpace = dev.getFreeSpace() / 1024 / 1024

            if freeSpace is not None and freeSpace < 1:
                tips.append("This device is nearly full (%.2f MB available). "
                            "This may prevent configuration." % freeSpace)
                icon = self.ICON_ERROR

            if life is not None and life < 0:
                tips.append("This devices is %d days old; battery life "
                            "may be limited." % dev.getAge())
                icon = max(icon, self.ICON_WARN)

            if calExp:
                calExpDate = datetime.fromtimestamp(calExp).date()
                if calExp < time.time():
                    tips.append("This device's calibration has expired on %s."
                                % calExpDate)
                    icon = max(icon, self.ICON_WARN)
                elif calExp < time.time() - 8035200:
                    tips.append("This device's calibration will expire on %s."
                                % calExpDate)
                    icon = max(icon, self.ICON_INFO)

        except (AttributeError, KeyError):
            pass

        if len(tips) == 0:
            self.listToolTips[index] = None
            self.listMsgs[index] = None
            return

        if icon > self.ICON_NONE:
            self.list.SetItemImage(index, icon)
        self.listToolTips[index] = '\n'.join(tips)
        self.listMsgs[index] = '\n'.join([u'\u2022 %s' % s for s in tips])


    def _thing2string(self, dev, col):
        """ Helper method for doing semi-smart formatting of a column. """
        try:
            return col.formatter(getattr(dev, col.propName, col.default))
        except TypeError:
            return col.default


    def populateList(self):
        """ Find recorders and add them to the list.
        """
        self.list.ClearAll()
        for i, c in enumerate(self.COLUMNS):
            self.list.InsertColumn(i, c[0])

        # Set minimum column widths (i.e. enough to fit the heading).
        # First column (which has an icon) is wider than the label.
        minWidths = [self.list.GetTextExtent(c[0])[0] + 16 for c in self.COLUMNS]
        minWidths[0] += 16

        self.recorders.clear()
        self.itemDataMap.clear()

        # This is to provide tool tips for individual list rows
        self.listMsgs = [None] * len(self.recorderPaths)
        self.listToolTips = [None] * len(self.recorderPaths)

        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))

        # For some reason, this wouldn't find devices if one of their files
        # is open (and only if it were opened via the Open File dialog).
        # See https://github.com/MideTechnology/SlamStickLab/issues/182
        # For now, don't restrict to the recorderPaths, find & fix real cause!
#         for dev in getDevices(self.recorderPaths):

        index = None
        for idx, dev in enumerate(getDevices()):
            try:
                index = self.list.InsertItem(idx, dev.path)
                self.recorders[index] = dev
                for i, col in enumerate(self.COLUMNS[1:], 1):
                    self.list.SetItem(index, i, self._thing2string(dev, col))
                    self.list.SetColumnWidth(i, wx.LIST_AUTOSIZE)
                    self.listWidth = max(self.listWidth,
                                         self.list.GetItemRect(index)[2])

                self.list.SetItemData(index, index)
                self.itemDataMap[index] = [getattr(dev, c.propName, c.default)
                                           for c in self.COLUMNS]

                if self.showWarnings:
                    self.setItemIcon(index, dev)

            except IOError:
                wx.MessageBox(
                    "An error occurred while trying to access a recorder (%s)."
                    "\n\nThe device's configuration data may be damaged. "
                    "Try disconnecting and reconnecting the device." % dev.path,
                    "Device Error", parent=self)
                if index is not None:
                    self.list.DeleteItem(index)

        for i, w in enumerate(minWidths):
            if self.list.GetColumnWidth(i) < w:
                self.list.SetColumnWidth(i, w)

        if self.firstDrawing:
            self.list.Fit()
            self.firstDrawing = False

        if not self.recorders or not self.selected:
            self.OnItemDeselected(None)

        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    def getSelected(self):
        """ Get the device corresponding to the selected item in the list.
        """
        if self.selected is None:
            return None
        return self.recorders.get(self.selected, None)


    def OnColClick(self, evt):
        # Required by ColumnSorterMixin
        evt.Skip()


    def OnItemSelected(self, evt):
        self.selected = self.list.GetItemData(evt.Item.GetId())
        if self.listMsgs[self.selected] is not None:
            self.infoText.SetLabel(self.listMsgs[self.selected])
        self.okButton.Enable(True)

        recorder = self.recorders.get(self.selected, None)
        if recorder.canRecord:
            self.recordButton.SetToolTip(self.RECORD_ENABLED)
            self.recordButton.Enable(True)
        else:
            self.recordButton.SetToolTip(self.RECORD_UNSUPPORTED)
            self.recordButton.Enable(False)

        evt.Skip()


    def OnItemDeselected(self, evt):
        self.selected = None
        self.okButton.Enable(False)
        if self.showWarnings:
            self.infoText.SetLabel("\n")
        else:
            self.infoText.SetLabel("")

        self.recordButton.Enable(False)
        self.recordButton.SetToolTip(self.RECORD_UNSELECTED)

        if evt is not None:
            evt.Skip()


    def OnItemDoubleClick(self, evt):
        if self.list.GetSelectedItemCount() > 0:
            # Close the dialog
            self.EndModal(wx.ID_OK)
        evt.Skip()


    def OnListMouseMotion(self, evt):
        """ Handle mouse movement, updating the tool tips, etc.
        """
        # This determines the list item under the mouse and shows the
        # appropriate tool tip, if any
        index, _ = self.list.HitTest(evt.GetPosition())
        if index != -1 and index != self.lastToolTipItem:
            item = self.list.GetItemData(index)
            if self.listToolTips[item] is not None:
                self.list.SetToolTip(self.listToolTips[item])
            else:
                self.list.UnsetToolTip()
            self.lastToolTipItem = index
        evt.Skip()


    def OnShow(self, evt):
        """ Handle dialog being shown/hidden.
        """
        if evt.IsShown():
            if self.autoUpdate:
                self.timer.Start(self.autoUpdate)
#                 print("XXX: timer started")
        else:
            self.timer.Stop()
#             print("XXX: timer stopped")
        evt.Skip()


    def setClocks(self, _evt=None):
        """ Set all clocks. Used as an event handler.
        """
        fails = []
        butts = self.okButton, self.cancelButton, self.setClockButton
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        for b in butts:
            b.Enable(False)

        for rec in self.recorders.values():
            try:
                rec.setTime()
            except Exception:  # as err:
                name = "%s SN:%s (%s)" % (rec.productName, rec.serial, rec.path)
                fails.append(name)
                # logger.error("%s setting clock on %s: %s" % (type(err).__name__, name, err))

        for b in butts:
            b.Enable(True)

        if fails:
            if len(fails) > 1:
                names = "\u2022 " + ('\n\u2022 '.join(fails))
                msg = ("Could not set recorder clocks.\n\n"
                       "Errors prevented the clocks being set on these recorders:\n\n"
                       "%s" % names)
            else:
                msg = ("Could not set recorder clock.\n\n"
                       "An error prevented the clock from being set on "
                       "recorder %s." % fails[0])

            wx.MessageBox(msg, "Device Error", parent=self,
                          style=wx.OK | wx.ICON_ERROR)

        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    def startRecording(self, _evt=None):
        """ Initiate a recording.
        """
        recorder = self.recorders.get(self.selected, None)
        if recorder and recorder.canRecord:
            recorder.startRecording()


#===============================================================================
#
#===============================================================================

def selectDevice(title="Select Recorder", parent=None, **kwargs):
    """ Display a device-selection dialog and return the path to a recorder.
        The dialog will (optionally) update automatically when devices are
        added or removed.

        :keyword title: A title string for the dialog
        :keyword autoUpdate: A number of milliseconds to delay between checks
            for changes to attached recorders. 0 will never update.
        :keyword parent: The parent window, if any.
        :keyword types: A list of possible recorder classes.
        :keyword showWarnings: If `True`, battery age and calibration
            expiration warnings will be shown for selected devices.
        :keyword hideClock: If `True`, the "Set all clocks" button will be
            hidden.
        :keyword hideRecord: If `True`, the "Start Recording" button will be
            hidden.
        :keyword okText: Alternate text to display on the OK/Configure button.
        :keyword okHelp: Alternate tooltip for the OK/Configure button.
        :keyword cancelText: Alternate text to display on the Cancel/Close
            button.
        :return: The path of the selected device.
    """
    result = None

    dlg = DeviceSelectionDialog(parent, -1, title, **kwargs)

    if dlg.ShowModal() == wx.ID_OK:
        result = dlg.getSelected()

    dlg.Destroy()
    if isinstance(result, dict):
        result = result.get('_PATH', None)
    return result


#===============================================================================
#
#===============================================================================

if __name__ == '__main__':
    app = wx.App()

    result = selectDevice(showAdvanced=True)  # hideClock=True, hideRecord=True)
    print("Result:", result)