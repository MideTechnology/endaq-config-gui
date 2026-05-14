import os.path
import random
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

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ===========================================================================
#
# ===========================================================================

FAKE_RECORDER = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             '_W5-D40_STM32_FwRev3.1.8')


# ===========================================================================
#
# ===========================================================================

def showName(method):
    def wrapped(instance, *args, **kwargs):
        logger.debug(f'Called {method.__name__}')
        return method(instance, *args, **kwargs)
    return wrapped


class MockCommandInterface(FileCommandInterface):
    """
    Mockup of minimal command interface for displaying the configuration UI.
    """

    def __init__(self, device, ap=False):
        self.ap = ap
        self.apNo = 8
        self.aps = [{'AuthType': 3, 'Known': True, 'RSSI': -58, 'SSID': 'MIDE-Guest', 'Selected': True}]
        self.aps.extend([{'AuthType': random.choice((0, 3)), 'Known': True,
                        'RSSI': random.randint(-8, 0) * 10, 'SSID': f'Example AP {n}',
                        'Selected': False} for n in range(self.apNo)])

        super().__init__(device)

    @showName
    def _getTime(self, pause=False, timeout=3) -> Tuple[Epoch, Epoch]:
        return time(), int(time())

    @showName
    def _setTime(self, t=None, pause=False, timeout=3) -> Tuple[Epoch, Epoch]:
        return time(), int(time())

    @showName
    def reset(self, *args, **kwargs) -> bool:
        return True

    @showName
    def isLocked(self, *args, **kwargs) -> tuple[bool, bool]:
        lockId = self.lockId[1]
        return (lockId and any(lockId)), lockId == self.hostId

    @showName
    def getLockID(self, *args, **kwargs) -> Union[bytearray, bytes, None]:
        return self.lockId[1]

    @showName
    def setLockID(self, current=None, new=None, **kwargs) -> Union[bytearray, bytes]:
        self.lockId = time(), new or self.hostId
        return True

    @showName
    def scanWifi(self, *args, **kwargs) -> Union[None, list]:
        while True:
            idx = random.randint(0, len(self.aps) - 1)
            if not self.aps[idx]['Selected']:
                break
        del self.aps[idx]

        self.apNo += 1
        newIdx = random.randint(0, len(self.aps))
        self.aps.insert(newIdx,
                        {'AuthType': random.choice((0, 3)), 'Known': True,
                        'RSSI': random.randint(-8, 0) * 10, 'SSID': f'Example AP {self.apNo}',
                        'Selected': False})
        return self.aps

    @showName
    def queryWifi(self, *args, **kwargs) -> Union[None, dict]:
        if self.ap:
            return {'SSID': 'Data Collection Box', 'WiFiConnectionStatus': 0x30, 'APN': '4g_apn'}
        return {'SSID': 'MIDE-Guest', 'WiFiConnectionStatus': 2}

    # @showName
    def setWifi(self, *args, **kwargs):
        logger.debug(f'setWifi({args}, {kwargs})')
        return

    @showName
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

    def __init__(self, path=FAKE_RECORDER, configUi=None, save=False, ap=False):
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
        self._command = MockCommandInterface(self, ap=ap)
        self._config = MockConfigInterface(self)
        self._config.configUi = configUiDoc
        self._config._saveConfig = save

        # Bug in endaq.device causes config dialog's use of dev.getCalPolynomials()
        # to fail if called before getCalibration() - to be fixed
        self.getCalibration()


# ===========================================================================
#
# ===========================================================================

def testConfigUi(configUi=None, path=FAKE_RECORDER, ap=False):
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
        recorder = MockRecorder(path, configUi, ap=ap)
        configureRecorder(recorder)

        if not (wx.GetKeyState(wx.WXK_CONTROL) and wx.GetKeyState(wx.WXK_SHIFT)):
            break
