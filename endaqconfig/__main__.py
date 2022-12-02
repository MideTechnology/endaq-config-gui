"""
__main__.py: allows the package to be run as a command-line utility.

This should contain as little code as possible, just what's related to
running from the command line.
"""
import wx

from .config_dialog import configureRecorder
from .widgets import device_dialog


def run():
    """ Run the configuration utility from the command line.
    """
    import argparse

    parser = argparse.ArgumentParser(description="enDAQ Configuration GUI")
    parser.add_argument("-a", '--advanced', action="store_true",
                        help="Show advanced configuration options")
    args = parser.parse_args()

    app = wx.App()
    try:
        dev = device_dialog.selectDevice(showAdvanced=args.advanced)
        wx.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        if dev:
            configureRecorder(dev, showAdvanced=args.advanced)
    finally:
        wx.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))



if __name__ == "__main__":
    run()
