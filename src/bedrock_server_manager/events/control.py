"""Cancellation is mutable only while before-operation listeners are running."""

from threading import Lock


class CancellableEvent:
    def __init__(self) -> None:
        self._is_cancelled = False
        self._cancel_reason: str | None = None
        self._sealed = False
        self._lock = Lock()

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    @property
    def cancel_reason(self) -> str | None:
        return self._cancel_reason

    def cancel(self, reason: str = "Cancelled by plugin") -> None:
        with self._lock:
            if not self._sealed and not self._is_cancelled:
                self._is_cancelled = True
                self._cancel_reason = str(reason)

    def seal(self) -> None:
        with self._lock:
            self._sealed = True
