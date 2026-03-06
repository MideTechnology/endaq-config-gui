from typing import Optional

import wx
import wx.lib.sized_controls as sc

from endaq.device.mqtt.discovery import findBrokers
from endaq.device.mqtt.mqtt_interface import MQTTConnector

from endaqconfig.widgets.shared import parseIP


import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # remove later


class BrokerDialog(sc.SizedDialog):
    """
    A dialog for connecting to an MQTT broker, either by selecting one that's
    advertised or 'manually' entering a broker IP address.
    """

    ID_CONNECT = wx.NewIdRef()


    def __init__(self,
                 parent,
                 defaultBroker=None,
                 defaultAddress='localhost:1883',
                 defaultField=0,
                 patterns: Optional[tuple[str]] = None,
                 **kwargs):
        """
        A dialog for connecting to an MQTT broker, either by selecting
        one that's advertised or 'manually' entering a broker IP address.

        :param parent: The parent window/dialog. Can be `None`.
        :param defaultBroker: The default advertised broker name. If `None` or it
            cannot be found, the first one in the list will be selected.
        :param defaultAddress: The default text in the broker address field.
        :param defaultField: The initial radio button selected, 0 for advertised,
            1 for manually-entered IP address.
        :param patterns: Zero or more MQTT Broker names (multiple positional
            arguments). Glob-like wildcards may be used (case-sensitive).
            `None` will return all MQTT brokers.
        :param scantime: The minimum time (in seconds) to scan for brokers. If
            any brokers are discovered in this time, they will be returned.
        :param timeout: The maximum time (in seconds) to scan for brokers, if
            none were found in `scantime`.
        :param callback: A function to call repeatedly while scanning. If the
            callback returns `True`, the wait for a response will be cancelled.
            The callback function should require no arguments.
        """
        self.defaultBroker = defaultBroker
        self.defaultAddress = defaultAddress
        super().__init__(parent, -1, "Select MQTT Broker",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.brokers = {}
        self.names = []

        # Arguments for `findBrokers()`
        self.patterns = patterns or (None,)
        self.scanKwargs = {k: kwargs.pop(k)
                           for k in ('timeout', 'scantime', 'patterns')
                           if k in kwargs}

        outerpane = self.GetContentsPane()
        outerpane.SetSizerType('vertical')
        pane = sc.SizedPanel(outerpane, -1)
        pane.SetSizerType('form')
        pane.SetSizerProps(expand=True)

        # First group: Select mDNS-advertised broker
        self.brokerRB = wx.RadioButton(pane, -1, 'Advertised Broker:', style=wx.RB_GROUP)
        self.brokerRB.SetSizerProps(valign='center')
        self.brokerRB.SetToolTip('Select an mDNS advertised broker by name')
        self.adpane = sc.SizedPanel(pane, -1)
        self.adpane.SetSizerType('horizontal')
        self.adpane.SetSizerProps(expand=True)
        self.brokerList = wx.Choice(self.adpane, -1, style=wx.BORDER_SUNKEN)
        self.brokerList.SetSizerProps(expand=True, proportion=1)
        self.scanBtn = wx.Button(self.adpane, -1, 'Rescan')
        self.scanBtn.Bind(wx.EVT_BUTTON, self.OnScanButton)
        self.scanBtn.SetToolTip('Update the list of advertised brokers')

        # Second group: Enter IP address explicitly
        self.ipRB = wx.RadioButton(pane, -1, 'Broker Address:')
        self.ipRB.SetSizerProps(valign='center')
        self.ipRB.SetToolTip('Enter the address of a non-advertised broker')
        self.ipField = wx.TextCtrl(pane, -1, self.defaultAddress)
        self.ipField.SetSizerProps(expand=True)
        self.ipField.SetToolTip('Enter a broker hostname or IP address\n'
                                "You may specify a non-standard port using ':' and the port number")

        # Connection error/bad address message
        self.errorText = wx.StaticText(outerpane, -1, '        ')
        self.errorText.SetSizerProps(expand=True, border=(['all'], 8), halign='center')
        self.errorText.SetForegroundColour(wx.RED)
        # self.errorText.SetFont(self.errorText.GetFont().Bold())

        # Bottom buttons: Connect (OK) and Cancel
        buttonpane = sc.SizedPanel(outerpane, -1)
        buttonpane.SetSizerType("horizontal")
        buttonpane.SetSizerProps(expand=True)
        sc.SizedPanel(buttonpane, -1).SetSizerProps(proportion=1)  # Spacer
        self.connectBtn = wx.Button(buttonpane, self.ID_CONNECT, 'Connect')
        self.connectBtn.SetSizerProps(halign="right")
        wx.Button(buttonpane, wx.ID_CANCEL).SetSizerProps(halign="right")

        self.Bind(wx.EVT_SHOW, self.OnShow)
        self.connectBtn.Bind(wx.EVT_BUTTON, self.OnConnectButton)
        self.Bind(wx.EVT_CHOICE, self.OnBrokerChoice)
        self.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self.enableGroup(defaultField)

        self.Fit()
        self.SetMinSize(self.GetSize())
        self.SetMaxSize((1000, self.GetSize().height))
        self.SetSize((500, self.GetSize().height))


    def enableGroup(self, groupNo):
        """ Explicitly set the radio buttons: 0 for advertised, 1 for
            manually-entered IP address.
        """
        self.adpane.Enable(groupNo == 0)
        self.ipField.Enable(groupNo == 1)


    def getSelectedName(self):
        idx = self.brokerList.GetSelection()
        if idx != wx.NOT_FOUND:
            return self.brokerList.GetString(idx)
        return None


    def getBrokers(self):
        """ Get advertised brokers and update the list.
        """
        try:
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
            self.connectBtn.Enable(False)
            self.errorText.SetLabel('')

            # If findBrokers() lags, it might be better to do it in a thread and post an event
            self.brokers = {b['name']: b for b in findBrokers(*self.patterns, **self.scanKwargs)}
            self.names = sorted(self.brokers)
            self.brokerList.Set(self.names)

            if self.defaultBroker in self.names:
                self.brokerList.SetSelection(self.names.index(self.defaultBroker))
            elif self.names:
                self.brokerList.SetSelection(0)
            self._setBrokerTooltip()

        finally:
            self.connectBtn.Enable(True)
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    def _setBrokerTooltip(self):
        """ Set the broker list tooltip to reflect the selected broker.
        """
        tt = ''
        broker = self.getSelectedName()
        if broker:
            info = self.brokers.get(broker)
            if info:
                tt = "{name}.{serviceType}\nIP {host[0]}, port {port}".format(**info)
        self.brokerList.SetToolTip(tt)


    def OnScanButton(self, _evt):
        """ Handle the 'Rescan' button press.
        """
        self.errorText.SetLabel('')
        current = self.getSelectedName()
        if current:
            self.defaultBroker = current
        self.getBrokers()


    def OnConnectButton(self, _evt):
        """ Handle the 'Connect' button press.
        """
        # TODO: Try connection. If good, post broker selection event and close dialog.
        #  If bad, show error message and continue
        self.errorText.SetLabel('')
        info = None
        if self.brokerRB.GetValue():
            info = self.brokers.get(self.getSelectedName())
            addr = '{host[0]}:{port}'.format(**info)
        else:
            addr = self.ipField.GetValue()

        try:
            # Test format and validity of the address (partially redundant
            # for advertised brokers, but relatively cheap to do)
            host, port = parseIP(addr, check=True)
            if self.ipRB.GetValue():
                info = {'name': f'{addr}',
                        'serviceType': '_endaq._tcp.local.',
                        'host': [host],
                        'port': port,
                        'properties': {}}
            logger.debug(f'👍 Address valid: {host}:{port}')
        except ValueError as err:
            self.errorText.SetLabel(f'⚠ {err}')
            return

        _ = info
        # TODO: 1. Create MQTTConnector, show error on failure
        # TODO: 2. Verify MQTTDeviceManager is running (maybe)
        # TODO: 3. Post event

        # Everything has passed, close the dialog
        self.EndModal(wx.ID_OK)


    def OnShow(self, evt):
        """ Handle dialog being shown/hidden.
        """
        if evt.IsShown():
            self.getBrokers()


    def OnRadioButton(self, evt):
        """ Handle the broker selection type radio button changing.
        """
        self.errorText.SetLabel('')
        but = evt.GetEventObject()
        self.enableGroup(0 if but == self.brokerRB else 1)


    def OnBrokerChoice(self, _evt):
        """ Handle a broker being selected from the list.
        """
        self._setBrokerTooltip()


if __name__ == '__main__':
    app = wx.App()
    with BrokerDialog(None) as dlg:
        dlg.ShowModal()
