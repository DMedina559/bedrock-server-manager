"""Nonserializable integration capabilities, separate from the data API."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
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


@asynccontextmanager
async def server_lifecycle_manager(
    server_name: str,
    stop_before: bool,
    start_after: bool = True,
    restart_on_success_only: bool = False,
    *,
    app_context: AppContext,
):
    """A context manager to safely stop and restart a server for an operation."""
    from ..api.models import StartServerRequest, StopServerRequest
    from ..api.server import start_server, stop_server

    server = app_context.get_server(server_name, require_installation=False)
    was_running = False
    operation_succeeded = True
    operation_cancelled = False
    original_error: BaseException | None = None

    # If the operation doesn't require a server stop, just yield and exit.
    if not stop_before:
        logger.debug("Stop/Start not flagged for '%s'. Skipping.", server_name)
        yield
        return

    try:
        # --- PRE-OPERATION: STOP SERVER ---

        if await server.is_running():
            logger.debug("Server '%s' is running. Stopping...", server_name)
            await stop_server(
                StopServerRequest(server_name=server_name), app_context=app_context
            )
            was_running = True
            logger.debug("Server '%s' stopped.", server_name)
        else:
            logger.debug("Server '%s' is not running. No stop needed.", server_name)

        # Yield control to the wrapped code block.
        yield

    except asyncio.CancelledError:
        original_error = asyncio.CancelledError()
        operation_cancelled = True
        operation_succeeded = False
        raise
    except Exception as error:
        # Retain the original failure's reporting ownership when re-raising.
        original_error = error
        operation_succeeded = False
        log_operation_error(
            logger,
            "Exception occurred during managed operation for '%s'.",
            server_name,
            error=error,
        )
        raise
    finally:
        # --- POST-OPERATION: RESTART SERVER ---
        # Only restart if the server was running initially and `start_after` is true.
        if was_running and start_after and not operation_cancelled:
            should_restart = True
            # If `restart_on_success_only` is set, check if the operation failed.
            if restart_on_success_only and not operation_succeeded:
                should_restart = False
                logger.warning(
                    "Operation for '%s' failed. Skipping restart as requested.",
                    server_name,
                )

            if should_restart:
                logger.debug("Restarting server '%s'...", server_name)
                try:
                    # Use the API function to ensure detached mode and proper handling.
                    await start_server(
                        StartServerRequest(server_name=str(server_name)),
                        app_context=app_context,
                    )
                    logger.debug("Server '%s' restart initiated.", server_name)
                except Exception as e:
                    log_operation_error(
                        logger, "FAILED to restart '%s': %s", server_name, e, error=e
                    )
                    # If the original operation succeeded, the failure to restart
                    # becomes the primary error to report.
                    if operation_succeeded:
                        raise
                    if original_error is not None:
                        original_error.add_note(
                            f"Server restart also failed: {type(e).__name__}"
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
