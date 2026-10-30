"""Nonserializable integration capabilities, separate from the data API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

from ..error import UserInputError
from ..logging import log_operation_error

if TYPE_CHECKING:
    from ..context import AppContext

logger = logging.getLogger(__name__)


async def run_task(
    target_function: Callable,
    *args: Any,
    app_context: AppContext,
    username: Optional[str] = None,
    plugin_name: str | None = None,
    **kwargs: Any,
) -> str:
    """Submit owned background work and return its task ID.

    Pass positional and keyword arguments through to the target function.
    """
    if "_plugin_owner" in kwargs:
        raise TypeError("Plugin ownership is injected by the runtime.")
    # Safely get the name, unwrapping functools.partial if necessary
    actual_func = getattr(target_function, "func", target_function)
    task_name = getattr(actual_func, "__name__", str(target_function))

    logger.debug("Running task in background: %s", task_name)

    return await app_context.task_manager.run_task(
        target_function, username, *args, _plugin_owner=plugin_name, **kwargs
    )


async def register_data_provider(
    topic: str,
    handler: Callable[..., Any],
    app_context: AppContext,
    plugin_name: Optional[str] = None,
) -> None:
    """Register an owner-scoped WebSocket topic provider."""
    if not topic:
        raise UserInputError("Topic name cannot be empty.")
    if not callable(handler):
        raise UserInputError("Data provider handler must be callable.")

    if not plugin_name:
        bound_self = getattr(handler, "__self__", None)
        if bound_self:
            api = getattr(bound_self, "api", None)
            plugin_name = getattr(api, "_plugin_name", None) or getattr(
                bound_self, "name", None
            )

    try:
        app_context.connection_manager.register_data_provider(
            topic=topic, handler=handler, plugin_name=plugin_name
        )
    except Exception as e:
        log_operation_error(
            logger,
            "Failed to register data provider for topic '%s': %s",
            topic,
            e,
            error=e,
        )
        raise


async def register_diagnostic_provider(
    name: str,
    handler: Callable[..., Any],
    *,
    app_context: AppContext,
    plugin_name: str | None = None,
) -> None:
    """Register asynchronous numeric metadata for this plugin's diagnostic section."""
    if not plugin_name:
        raise UserInputError("Plugin diagnostics require an explicit owner")
    app_context.events.check_owner(f"plugin:{plugin_name}")
    app_context.diagnostics.register(
        f"plugin:{plugin_name}:{name}", handler, owner=f"plugin:{plugin_name}"
    )


async def report_task_progress(
    percent: float, *, app_context: AppContext, plugin_name: str | None = None
) -> None:
    """Report progress for the plugin's current managed task without exposing a context."""
    app_context.task_manager.report_progress(percent, plugin_owner=plugin_name)


async def report_task_stage(
    message: str, *, app_context: AppContext, plugin_name: str | None = None
) -> None:
    """Publish a safe, short description for the plugin's current managed task."""
    await app_context.task_manager.report_plugin_stage(
        message, plugin_owner=plugin_name
    )


async def read_plugin_file(filename: str, *, app_context: AppContext, plugin_name: str):
    """Read a JSON file from this plugin's configuration directory."""
    from ..utils.threads import run_in_thread
    from .files import read_plugin_json

    return await run_in_thread(
        read_plugin_json, app_context.config_dir, plugin_name, filename
    )


async def write_plugin_file(
    filename: str, value: Any, *, app_context: AppContext, plugin_name: str
) -> None:
    """Atomically write JSON inside this plugin's configuration directory."""
    from ..utils.threads import run_in_thread
    from .files import write_plugin_json

    await run_in_thread(
        write_plugin_json, app_context.config_dir, plugin_name, filename, value
    )


def register_scheduled_task(
    name: str,
    handler: Callable[..., Any],
    *,
    app_context: AppContext,
    plugin_name: str,
    options_model=None,
    timeout_seconds=300,
    requires_server_lock=True,
    with_context=False,
):
    """Register an async ``plugin_name:task`` handler accepting server_name and options.

    Administrators create schedules separately. Unloaded owners cannot run tasks.
    """
    owner = f"plugin:{plugin_name}"
    bus = app_context.events
    app_context.scheduler.register(
        name,
        handler,
        owner=owner,
        generation=bus.owner_generation(owner),
        options_model=options_model,
        timeout_seconds=timeout_seconds,
        requires_server_lock=requires_server_lock,
        with_context=with_context,
    )
