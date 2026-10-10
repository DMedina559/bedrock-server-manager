"""Ordering metadata shared by HTTP observations and WebSocket state updates.

Reserve before asynchronous reads or delivery. Revisions are comparable only
within one backend process epoch, never across restarts or worker processes.
"""

from threading import Lock
from typing import TypedDict
from uuid import uuid4


class StateStamp(TypedDict):
    epoch: str
    revision: int


class StateClock:
    """A thread-safe, JavaScript-safe sequence for one backend instance."""

    def __init__(self) -> None:
        self.epoch = str(uuid4())
        self._revision = 0
        self._lock = Lock()

    def capture(self) -> StateStamp:
        with self._lock:
            if self._revision >= 2**53 - 1:
                raise OverflowError("State revision exhausted")
            self._revision += 1
            return {"epoch": self.epoch, "revision": self._revision}


state_clock = StateClock()
