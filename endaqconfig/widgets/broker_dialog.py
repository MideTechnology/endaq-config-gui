from dataclasses import asdict
from typing import Any, Dict, Optional

import wx
import wx.lib.sized_controls as sc

from endaq.device.mqtt.discovery import findBrokers, MDNSInfo

from endaqconfig.widgets.shared import parseIP
from endaqconfig.widgets import events
from endaqconfig.widgets.threads import BrokerConnectThread

import logging
logger = logging.getLogger(__name__)


class BrokerDialog(sc.SizedDialog):
    """
    A dialog for connecting to an MQTT broker, either by selecting one that's
    advertised or 'manually' entering a broker IP address.
    """


    # TODO: REMOVE NEXT COMMENT LATER (linter doesn't like monkeypatched sizer methods, clutters everything up)
    # noinspection PyUnresolvedReferences
    def __init__(self,
                 parent,
                 root=None,
                 defaultBroker=None,
                 defaultAddress='localhost:1883',
                 defaultField=0,
                 patterns: Optional[tuple[str]] = None,
                 clientArgs: Dict[str, Any] = None,
                 connectArgs: Dict[str, Any] = None,
                 **kwargs):
        """
        A dialog for connecting to an MQTT broker, either by selecting
        one that's advertised or 'manually' entering a broker IP address.

        :param parent: The parent window/dialog. Can be `None`.
        :param root: The 'root' dialog, i.e., `DeviceSelectionDialog`, in case
            `parent` isn't it (`parent` might be a child of the root dialog).
            `None` (default) will use `parent`.
        :param defaultBroker: The default advertised broker name. If `None` or it
            cannot be found, the first one in the list will be selected.
        :param defaultAddress: The default text in the broker address field.
        :param defaultField: The initial radio button selected, 0 for advertised,
            1 for manually-entered IP address.
        :param patterns: Zero or more MQTT Broker names (multiple positional
            arguments). Glob-like wildcards may be used (case-insensitive).
            `None` will return all MQTT brokers.
        :param scantime: The minimum time (in seconds) to scan for brokers. If
            any brokers are discovered in this time, they will be returned.
        :param timeout: The maximum time (in seconds) to scan for brokers, if
            none were found in `scantime`.
        :param callback: A function to call repeatedly while scanning. If the
            callback returns `True`, the wait for a response will be cancelled.
            The callback function should require no arguments.
        """
        self.root = root or parent
        self.defaultBroker = defaultBroker
        self.defaultAddress = defaultAddress
        self.clientArgs = clientArgs
        self.connectArgs = connectArgs
        super().__init__(parent, -1, "Select MQTT Broker",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.brokers: Dict[str, MDNSInfo] = {}
        self.names: List[str] = []
        self.thread = None

        # Arguments for `findBrokers()`. Rarely used, but could be.
        self.patterns = patterns or (None,)
        self.scanKwargs = {k: kwargs.pop(k)
                           for k in ('timeout', 'scantime', 'patterns')
                           if k in kwargs}

        self.activeGroup = defaultField

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
        self.errorText = wx.StaticText(outerpane, -1, ' '*40)
        self.errorText.SetSizerProps(expand=True, border=(['all'], 8), halign='center')
        self.textColorNormal = self.errorText.GetForegroundColour()
        self.textColorError = wx.RED

        # Bottom buttons: Connect (OK) and Cancel
        buttonpane = sc.SizedPanel(outerpane, -1)
        buttonpane.SetSizerType("horizontal")
        buttonpane.SetSizerProps(expand=True)
        sc.SizedPanel(buttonpane, -1).SetSizerProps(proportion=1)  # Spacer
        self.connectBtn = wx.Button(buttonpane, -1, 'Connect')
        self.connectBtn.SetSizerProps(halign="right")
        wx.Button(buttonpane, wx.ID_CANCEL).SetSizerProps(halign="right")

        self.Bind(wx.EVT_SHOW, self.OnShow)
        self.connectBtn.Bind(wx.EVT_BUTTON, self.OnConnectButton)
        self.Bind(wx.EVT_CHOICE, self.OnBrokerChoice)
        self.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self.enableGroup(defaultField)

        self.connectFailTimer = wx.Timer(self)
        self.connectThread = None

        self.Bind(events.EVT_MQTT_CONNECTING, self.OnMQTTConnecting)
        self.Bind(events.EVT_BROKER_SELECTED, self.OnBrokerSelected)
        self.Bind(events.EVT_MQTT_ERROR, self.OnMQTTError)
        self.Bind(wx.EVT_TIMER, self.OnConnectFailTimer, id=self.connectFailTimer.GetId())

        self.Fit()
        self.SetMinSize(self.GetSize())
        self.SetMaxSize((1000, self.GetSize().height))
        self.SetSize((500, self.GetSize().height))


    def enableGroup(self, groupNo):
        """ Explicitly set the radio buttons: 0 for advertised, 1 for
            manually-entered IP address.
        """
        self.activeGroup = groupNo
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
            self.Enable(False)
            self.setMessage('')

            # If findBrokers() lags, it might be better to do it in a thread and post an event
            self.brokers = {b.name: b for b in findBrokers(*self.patterns, **self.scanKwargs,
                                                           persistent=True)}
            self.names = sorted(self.brokers)
            self.brokerList.Set(self.names)

            if self.defaultBroker in self.names:
                self.brokerList.SetSelection(self.names.index(self.defaultBroker))
            elif self.names:
                self.brokerList.SetSelection(0)
            self._setBrokerTooltip()

        finally:
            self.Enable(True)
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    def _setBrokerTooltip(self):
        """ Set the broker list tooltip to reflect the selected broker.
        """
        tt = ''
        broker = self.getSelectedName()
        if broker:
            info = self.brokers.get(broker)
            if info:
                tt = "{name}.{serviceType}\nIP {host[0]}, port {port}".format(**asdict(info))
        self.brokerList.SetToolTip(tt)


    def setMessage(self, message: str, error=False):
        """ Set the message area text.

            :param message: Message text.
            :param error: If `True`, use the error font color and show
                message with a warning icon.
        """
        if error:
            color = self.textColorError
            message = f'⚠ {message}'
        else:
            color = self.textColorNormal

        self.errorText.SetForegroundColour(color)
        self.errorText.SetLabel(message)


    def startConnectThread(self, info: Dict[str, Any]):
        """ Kick off the `BrokerConnectThread` thread.
        """
        self.Enable(False)  # Doesn't look disabled; explicitly disable widgets?

        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        self.connectFailTimer.StartOnce(30000)
        self.thread = BrokerConnectThread(self, self.root, info,
                                          connectArgs=self.connectArgs,
                                          clientArgs=self.clientArgs)


    # =======================================================================
    #
    # =======================================================================

    def OnScanButton(self, _evt):
        """ Handle the 'Rescan' button press.
        """
        self.setMessage('')
        current = self.getSelectedName()
        if current:
            self.defaultBroker = current
        self.getBrokers()


    def OnConnectButton(self, _evt):
        """ Handle the 'Connect' button press.
        """
        self.setMessage('')
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
                # Create broker info like `findBrokers()`
                info = {'name': f'{addr}',
                        'serviceType': '_endaq._tcp.local.',
                        'host': [host],
                        'port': port,
                        'properties': {}}
            logger.debug(f'👍 Address valid: {host}:{port}')

        except ValueError as err:
            self.setMessage(str(err), error=True)
            return

        self.startConnectThread(info)


    def OnShow(self, evt):
        """ Handle dialog being shown/hidden.
        """
        if evt.IsShown():
            self.getBrokers()
        else:
            self.connectFailTimer.Stop()
            if self.thread and self.thread.is_alive():
                logger.debug("BrokerDialog closing, but BrokerConnectThread still running!")


    def OnRadioButton(self, evt):
        """ Handle the broker selection type radio button changing.
        """
        self.setMessage('')
        but = evt.GetEventObject()
        self.enableGroup(0 if but == self.brokerRB else 1)


    def OnBrokerChoice(self, _evt):
        """ Handle a broker being selected from the list.
        """
        self._setBrokerTooltip()


    # =======================================================================
    #
    # =======================================================================

    def OnMQTTConnecting(self, _evt):
        """ Handle the start of an attempt to connect to a broker. Event
            posted by `BrokerConnectThread`.
        """
        self.setMessage('Connecting...')


    def OnBrokerSelected(self, evt):
        """ Handle (ostensibly) successful `MQTTConnector` creation. Event
            posted by `BrokerConnectThread`.
        """
        if self.root:
            wx.PostEvent(self.root, evt)
        self.EndModal(wx.ID_OK)


    def OnMQTTError(self, evt):
        """ Handle an MQTT-related error event.
        """
        self.connectFailTimer.Stop()
        self.Enable()
        self.connectBtn.Enable()
        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))

        self.setMessage(evt.message, error=True)


    def OnConnectFailTimer(self, _evt):
        """ Handle a contingency timeout event (i.e., the `BrokerConnectThread`
            failed in some unexpected way).
        """
        evt = events.EvtMQTTError("Timed out starting broker connection")
        wx.PostEvent(self, evt)


# ===========================================================================
# DIALOG TEST CODE. REMOVE LATER.
# ===========================================================================

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    app = wx.App()
    with BrokerDialog(None) as dlg:
        dlg.ShowModal()
