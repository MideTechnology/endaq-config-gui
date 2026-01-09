import os.path
from time import time
from typing import Union, Tuple, Optional, Callable

from ebmlite import loadSchema
from ebmlite.util import loadXml

from endaq.device import Epoch
from endaq.device.base import Recorder
from endaq.device.command_interfaces import FileCommandInterface
from endaq.device.config import FileConfigInterface
from endaq.device.devinfo import FileDeviceInfo

from endaqconfig.config_dialog import configureRecorder

import wx

# ===========================================================================
#
# ===========================================================================

FAKE_RECORDER = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             '_W5-D40_STM32_FwRev3.1.8')


# ===========================================================================
#
# ===========================================================================

class MockCommandInterface(FileCommandInterface):
    """
    Mockup of minimal command interface for displaying the configuration UI.
    """

    def _getTime(self, pause=False, timeout=3) -> Tuple[Epoch, Epoch]:
        return time(), int(time())

    def _setTime(self, t=None, pause=False, timeout=3) -> Tuple[Epoch, Epoch]:
        return time(), int(time())

    def reset(self, *args, **kwargs) -> bool:
        return True

    def isLocked(self, *args, **kwargs) -> tuple[bool, bool]:
        lockId = self.lockId[1]
        return (lockId and any(lockId)), lockId == self.hostId

    def getLockID(self, *args, **kwargs) -> Union[bytearray, bytes, None]:
        return self.lockId[1]

    def setLockID(self, current=None, new=None, **kwargs) -> Union[bytearray, bytes]:
        self.lockId = time(), new or self.hostId
        return True

    def scanWifi(self, *args, **kwargs) -> Union[None, list]:
        return  [{'AuthType': 3, 'Known': True, 'RSSI': -58, 'SSID': 'MIDE-Guest', 'Selected': True},
                 {'AuthType': 3, 'Known': False, 'RSSI': -58, 'SSID': 'Example AP 1', 'Selected': False},
                 {'AuthType': 3, 'Known': False, 'RSSI': -81, 'SSID': 'Example AP 2', 'Selected': False},
                 {'AuthType': 3, 'Known': False, 'RSSI': -83, 'SSID': 'Example AP 3', 'Selected': False}]

    def queryWifi(self, *args, **kwargs) -> Union[None, dict]:
        return {'SSID': 'MIDE-Guest', 'WiFiConnectionStatus': 2}

    def setWifi(self, *args, **kwargs):
        return

    def _setInfo(self, *args, **kwargs):
        return True


class MockConfigInterface(FileConfigInterface):
    _saveConfig = False

    def _writeConfig(self, data: bytes) -> int:
        if self._saveConfig:
            return super()._writeConfig(data)
        return len(data)

    def getConfigUI(self):
        if self.device._configUi is None:
            return super().getConfigUI()
        return self.device._configUi


# ===========================================================================
#
# ===========================================================================

class MockRecorder(Recorder):
    """
    Minimal `Recorder` for displaying the configuration UI.
    """
    configUiDoc = None

    def __init__(self, path=FAKE_RECORDER, configUi=None, save=False):
        """
        Minimal `Recorder` for displaying the configuration UI.

        :param path: The path to a 'base' fake recorder directory.
        :param configUi: A file of CONFIG.UI data, either XML or EBML.
            `None` will use the fake recorder's CONFIG.UI file.
        :param save: If `True`, the dialog will write `config.cfg` on
            save.
        """
        if configUi:
            schema = loadSchema('mide_config_ui.xml')
            if configUi.lower().endswith('.xml'):
                # configUiDoc = loadXml(configUi, schema, ':memory:')
                configUiDoc = loadXml(configUi, schema)
            else:
                configUiDoc = schema.load(configUi)
                if len(configUiDoc) == 0 or configUiDoc[0].name != 'ConfigUI':
                    raise ValueError(f'Could not read {configUi} (not XML or CONFIG.UI)')
        else:
            configUiDoc = None

        self._configUi = configUiDoc

        super().__init__(path, strict=False)
        self._devinfo = FileDeviceInfo(self)
        self._command = MockCommandInterface(self)
        self._config = MockConfigInterface(self)
        self._config.configUi = configUiDoc
        self._config._saveConfig = save

        # Bug in endaq.device causes config dialog's use of dev.getCalPolynomials()
        # to fail if called before getCalibration() - to be fixed
        self.getCalibration()


# ===========================================================================
#
# ===========================================================================

def testConfigUi(configUi=None, path=FAKE_RECORDER):
    """
    Render a configuration dialog, using provided CONFIG.UI data. Clicking
    'Cancel' while holding Ctrl+Shift will reload the CONFIG.UI data.

    :param configUi: A file of CONFIG.UI data, either XML or EBML.
        `None` will use the fake recorder's CONFIG.UI file.
    :param path: The path to a 'base' fake recorder directory.
    """
    if not wx.GetApp():
        _app = wx.App()

    while True:
        recorder = MockRecorder(path, configUi)
        configureRecorder(recorder)

        if not (wx.GetKeyState(wx.WXK_CONTROL) and wx.GetKeyState(wx.WXK_SHIFT)):
            break
