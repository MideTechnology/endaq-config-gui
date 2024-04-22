"""
A GUI for configuring enDAQ data recoders. This can be run standalone, or
imported into another script.
"""

__version__ = "2.0.0b1"

import logging

logger = logging.getLogger('endaqconfig')
logger.setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s")

