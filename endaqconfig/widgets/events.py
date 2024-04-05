"""
Custom events used in the device-related dialogs.
"""

from wx.lib.newevent import NewEvent

EvtConfigButton, EVT_CONFIG_BUTTON = NewEvent()
EvtRecordButton, EVT_RECORD_BUTTON = NewEvent()


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
