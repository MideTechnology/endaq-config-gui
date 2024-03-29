"""
__main__.py: allows the package to be run as a command-line utility.

This should contain as little code as possible, just what's related to
running from the command line.
"""
import logging
import wx

from endaq.device import getRecorder

from .config_dialog import __DEBUG__, configureRecorder, logger
from .widgets import device_dialog


def run(debug=__DEBUG__):
    """ Run the configuration utility from the command line.
    """
    import argparse

    parser = argparse.ArgumentParser(description="enDAQ Configuration GUI")
    parser.add_argument("-a", '--advanced', action="store_true",
                        help="Show advanced configuration options")
    parser.add_argument("-D", '--debug', action="store_true",
                        help="Run in 'debug' mode, showing extra messages, etc.")
    parser.add_argument("path", nargs='?',
                        help=("The path of the device to configure (optional). "
                              "Foregoes displaying the device list."))
    args = parser.parse_args()

    debug = debug or args.debug
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Starting in DEBUG mode.")

    # Create a wx.App if one not already running (the latter is an edge case).
    _app = wx.GetApp()
    if not _app:
        _app = wx.App()

    try:
        if not args.path:
            dev = device_dialog.selectDevice(showAdvanced=args.advanced,
                                             debug=debug)
        else:
            dev = getRecorder(args.path)
            if not dev:
                wx.MessageBox(f'Could not find a valid enDAQ device on path "{args.path}"',
                              'enDAQ Configuration Error',  style=wx.OK | wx.ICON_ERROR | wx.CENTRE)
                return

        wx.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        if dev:
            configureRecorder(dev,
                              showAdvanced=args.advanced,
                              exceptions=False,
                              debug=debug)
    finally:
        wx.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


if __name__ == "__main__":
    run()
