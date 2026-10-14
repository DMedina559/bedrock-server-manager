"""Bounded lifecycle stages with explicit task ownership and diagnostics."""

import asyncio
import inspect
import logging
import time
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ..diagnostics.service import Diagnostics

logger = logging.getLogger(__name__)
_pending: set[asyncio.Task] = set()


class LifecyclePhase(StrEnum):
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


def is_application_ready(
    phase: str, *, state_loaded: bool, web_phase: str | None = None
) -> bool:
    """Require loaded state and ready application/web runtimes without starting services."""
    return (
        state_loaded
        and phase == LifecyclePhase.READY
        and (web_phase is None or web_phase == LifecyclePhase.READY)
    )


def _consume(task: asyncio.Task) -> None:
    _pending.discard(task)
    if not task.cancelled():
        task.exception()


async def run_stage(
    name: str,
    action: Callable[[], Any],
    timeout: float,
    grace: float,
    *,
    owned_tasks: set[asyncio.Task] | None = None,
    diagnostics: "Diagnostics | None" = None,
) -> None:
    """Cancel overdue work without waiting indefinitely for cancellation handlers."""

    async def invoke() -> None:
        result = action()
        if inspect.isawaitable(result):
            await result

    started = time.monotonic()
    failure: BaseException | None = None
    if diagnostics is not None:
        diagnostics.stage = name
        diagnostics.stage_started_at = time.time()
        diagnostics.stage_started_monotonic = started
        diagnostics.stage_timeout_seconds = timeout
    task = asyncio.create_task(invoke(), name=f"lifecycle:{name}")
    _pending.add(task)
    task.add_done_callback(_consume)
    if owned_tasks is not None:
        owned_tasks.add(task)
        task.add_done_callback(owned_tasks.discard)
    logger.debug("Lifecycle stage '%s' started (deadline %.1fs).", name, timeout)
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if not done:
            raise TimeoutError(f"Lifecycle stage '{name}' exceeded {timeout:g}s")
        if task.cancelled():
            raise RuntimeError(f"Lifecycle stage '{name}' was cancelled")
        task.result()
    except BaseException as error:
        failure = error
        if not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=grace)
            if not task.done():
                logger.error(
                    "Lifecycle stage '%s' did not stop within %.1fs of cancellation.",
                    name,
                    grace,
                )
        logger.error(
            "Lifecycle stage '%s' failed after %.2fs.",
            name,
            time.monotonic() - started,
            exc_info=True,
        )
        raise
    else:
        logger.debug(
            "Lifecycle stage '%s' completed in %.2fs.", name, time.monotonic() - started
        )
    finally:
        if diagnostics is not None:
            diagnostics.record("lifecycle", name, started=started, error=failure)
            if diagnostics.stage == name:
                diagnostics.stage = None
                diagnostics.stage_started_at = None
                diagnostics.stage_started_monotonic = None
                diagnostics.stage_timeout_seconds = None
