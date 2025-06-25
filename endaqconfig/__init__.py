"""
A GUI for configuring enDAQ data recoders. This can be run standalone, or
imported into another script.
"""

__version__ = "2.0.4"
__author__ = "David Stokes"
__copyright__ = "Copyright 2025 Mide Technology Corporation"

import logging

logger = logging.getLogger('endaqconfig')
logger.setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s")
