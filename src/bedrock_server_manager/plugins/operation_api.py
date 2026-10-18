"""Owner-scoped read access to the caller's live operation sequence."""

from typing import Any, Callable, cast

from ..operations import OperationResultQuery, OperationSequence, OperationSnapshot


class PluginOperationAPI:
    def __init__(self, dispatch: Callable[..., Any]):
        self._dispatch = dispatch

    def current(self) -> OperationSnapshot | None:
        """Return the current operation, or None outside an operation."""
        return cast(OperationSnapshot | None, self._dispatch("operation_current"))

    def sequence(self) -> OperationSequence | None:
        """Return immutable ancestry and retention information."""
        return cast(OperationSequence | None, self._dispatch("operation_sequence"))

    def results(
        self, query: OperationResultQuery | None = None
    ) -> tuple[OperationSnapshot, ...]:
        """Read finished results, oldest first, only from the current sequence."""
        return cast(
            tuple[OperationSnapshot, ...], self._dispatch("operation_results", query)
        )
