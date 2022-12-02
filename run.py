"""
Run the config GUI. Mainly for testing, may be removed.
Basically the same as `config_dialog.__main__()`, but can be run directly.
"""

import wx

from config_dialog.config_dialog import configureRecorder
from config_dialog.widgets import device_dialog

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="enDAQ Configuration GUI")
    parser.add_argument("-a", '--advanced', action="store_true",
                        help="Show advanced configuration options")
    args = parser.parse_args()

    app = wx.App()
    dev = device_dialog.selectDevice(showAdvanced=args.advanced)
    if dev:
        configureRecorder(dev, showAdvanced=args.advanced)