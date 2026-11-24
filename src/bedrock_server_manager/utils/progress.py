"""Task-local stage reporting without a dependency on a transport or task manager."""

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_reporter: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "operation_stage_reporter", default=None
)


@contextmanager
def progress_scope(reporter: Callable[[str], Awaitable[None]]) -> Iterator[None]:
    """Bind stages to the managed operation and restore the caller's reporter."""
    token = _reporter.set(reporter)
    try:
        yield
    finally:
        _reporter.reset(token)


async def report_stage(message: str) -> None:
    """Report a safe stage description when a managed task owns this context."""
    reporter = _reporter.get()
    if reporter is not None:
        await reporter(message)
