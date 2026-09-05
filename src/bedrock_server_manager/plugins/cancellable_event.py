from typing import Optional


class CancellableEvent:
    """An event object that can be passed to plugins to allow them to cancel a core operation."""

    def __init__(self) -> None:
        self._is_cancelled: bool = False
        self._cancel_reason: Optional[str] = None

    @property
    def is_cancelled(self) -> bool:
        """Returns True if the event has been cancelled by a plugin."""
        return self._is_cancelled

    @property
    def cancel_reason(self) -> Optional[str]:
        """Returns the reason for cancellation, if any."""
        return self._cancel_reason

    def cancel(self, reason: str = "Cancelled by plugin") -> None:
        """
        Cancels the ongoing core operation.

        Args:
            reason (str): The reason for cancelling the event. Defaults to "Cancelled by plugin".
        """
        self._is_cancelled = True
        self._cancel_reason = reason
