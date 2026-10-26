"""Owner-scoped read access to the caller's live operation sequence."""

from contextlib import contextmanager
from typing import Any, Callable, Iterator, cast

from ..operations import (
    OperationActivity,
    OperationActivityQuery,
    OperationResultQuery,
    OperationSequence,
    OperationSnapshot,
)


class PluginOperationAPI:
    def __init__(self, dispatch: Callable[..., Any]):
        self._dispatch = dispatch

    def activity(
        self, query: OperationActivityQuery | None = None
    ) -> OperationActivity:
        """Read bounded metadata across all sequences; results() stays sequence-local."""
        return cast(OperationActivity, self._dispatch("operation_activity", query))

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

    @contextmanager
    def scope(
        self, name: str, *, server_name: str | None = None
    ) -> Iterator[OperationSnapshot]:
        """Track namespaced plugin work; core operation names remain unavailable."""
        with self._dispatch(
            "operation_scope", name, server_name=server_name
        ) as operation:
            yield operation
