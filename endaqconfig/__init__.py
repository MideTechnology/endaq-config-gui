"""
A GUI for configuring enDAQ data recoders. This can be run standalone, or
imported into another script.
"""

__version__ = "2.0.4"
__author__ = "David Stokes"
__copyright__ = "Copyright 2025 Mide Technology Corporation"

import sys
import logging

logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)
logger.setLevel(logging.DEBUG)
# logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s")
logging.basicConfig(format="%(asctime)s %(threadName)s %(filename)s %(funcName)s %(levelname)s: %(message)s")


# ===========================================================================
# Exception handling
# ===========================================================================

# Some environments (e.g., PyCharm) change `sys.excepthook`; keep track of it
# so it can be used for exceptions other than the anticipated one.
_OLD_EXCEPTHOOK = sys.excepthook


def wxSafeExcepthook(ex_type, ex, traceback):
    """ `excepthook` function to suppress RuntimeErrors (related to accessing
        deleted wxPython objects) that can occur during wxPython shutdown
        when there are multiple threads and/or timers.
    """
    if isinstance(ex, RuntimeError) and 'has been deleted' in str(ex):
        logger.debug(f'Ignoring anticipated RuntimeError during shutdown: {ex!r}')
    else:
        # Use the default excepthook (may not be `sys.__excepthook__` in IDEs)
        _OLD_EXCEPTHOOK(ex_type, ex, traceback)


# Install the custom excepthook
sys.excepthook = wxSafeExcepthook

