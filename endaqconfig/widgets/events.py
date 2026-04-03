"""
Custom events used in the device-related dialogs.
"""

from wx.lib.newevent import NewEvent


# ===========================================================================
# Device selection/control dialog events
# ===========================================================================

# Configure a device. Carries `device` as attribute.
EvtConfig, EVT_CONFIG = NewEvent()

# Start (or stop) a recording. Carries `device` as attribute.
EvtRecord, EVT_RECORD = NewEvent()

# Start (or stop) a stream. Carries `device` as attribute.
EvtStream, EVT_STREAM = NewEvent()

# Lock (or unlock) a device
EvtLockDevice, EVT_LOCK_DEVICE = NewEvent()

# Blink the recorder's LED.
EvtBlink, EVT_BLINK = NewEvent()


# ===========================================================================
# Wi-Fi events
# ===========================================================================

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


# ===========================================================================
# Remote/MQTT-related events
# ===========================================================================

# New broker selected in UI. Events should have a `broker` attribute
# containing a dictionary of broker info.
EvtBrokerUpdate, EVT_BROKER_UPDATE = NewEvent()

# Connection/disconnection events. `EvtMQTTDisconnected`
EvtMQTTConnecting, EVT_MQTT_CONNECTING = NewEvent()
EvtMQTTConnected, EVT_MQTT_CONNECTED = NewEvent()

# Disconnect event. Posted after normal disconnection and disconnections
# that are (or are caused by) errors. All events should have an `error`
# attribute, and errors should have a `message`.
EvtMQTTDisconnected, EVT_MQTT_DISCONNECTED = NewEvent()

# An MQTT-related error, but not one that dropped the connection. Events
# should have a `message` attribute.
EvtMQTTError, EVT_MQTT_ERROR = NewEvent()
