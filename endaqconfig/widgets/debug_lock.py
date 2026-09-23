"""
`threading.RLock` replacement for debugging. To be removed before release.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class DebugRLock:
    """ `threading.RLock` replacement for debugging.
    """

    def __init__(self, name=None):
        self.name = name or type(self).__name__
        self._lock = threading.RLock()


    def acquire(self, blocking=True, timeout=-1):
        logger.debug(f'{self.name} acquiring lock')
        return self._lock.acquire(blocking=blocking, timeout=timeout)


    def release(self, *args):
        logger.debug(f'{self.name} releasing lock')
        return self._lock.release()

    __enter__ = acquire
    __exit__ = release
