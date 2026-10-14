"""Ordering metadata shared by HTTP observations and WebSocket state updates.

Reserve before asynchronous reads or delivery. Revisions are comparable only
within one backend process epoch, never across restarts or worker processes.
"""

from threading import Lock
from typing import Self, TypedDict
from uuid import uuid4

from pydantic import Field, model_validator

from .contracts import DataContract


class StateRevision(DataContract):
    """Optional for legacy producers; compare revisions only within an epoch."""

    epoch: str | None = None
    revision: int | None = Field(default=None, ge=1, le=2**53 - 1)

    @model_validator(mode="after")
    def validate_revision_pair(self) -> Self:
        if self.epoch is not None and not self.epoch.strip():
            raise ValueError("epoch must not be blank")
        if (self.epoch is None) != (self.revision is None):
            raise ValueError("epoch and revision must be supplied together")
        return self


class RevisionStamp(TypedDict):
    epoch: str
    revision: int


class RevisionClock:
    """A thread-safe, JavaScript-safe sequence for one backend instance."""

    def __init__(self) -> None:
        self.epoch = str(uuid4())
        self._revision = 0
        self._lock = Lock()

    def capture(self) -> RevisionStamp:
        with self._lock:
            if self._revision >= 2**53 - 1:
                raise OverflowError("State revision exhausted")
            self._revision += 1
            return {"epoch": self.epoch, "revision": self._revision}


revision_clock = RevisionClock()
