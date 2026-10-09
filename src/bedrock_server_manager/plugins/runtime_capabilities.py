"""Nonserializable integration capabilities, separate from the data API."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Callable, Optional

from ..error import BSMError, UserInputError
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
    """Submits a function to be run in the background by the TaskManager.

    Args:
        target_function (Callable): The function to execute.
        app_context (AppContext): The application context.
        username (Optional[str], optional): The user associated with the task for WebSocket notifications.
        *args (Any): Positional arguments for the target function.
        **kwargs (Any): Keyword arguments for the target function.

    Returns:
        str: The ID of the created task.
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

    server = app_context.get_server(server_name)
    was_running = False
    operation_succeeded = True
    operation_cancelled = False

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
        operation_cancelled = True
        operation_succeeded = False
        raise
    except Exception as error:
        # Retain the original failure's reporting ownership when re-raising.
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
                except BSMError as e:
                    log_operation_error(
                        logger, "FAILED to restart '%s': %s", server_name, e, error=e
                    )
                    # If the original operation succeeded, the failure to restart
                    # becomes the primary error to report.
                    if operation_succeeded:
                        raise


async def register_data_provider(
    topic: str,
    handler: Callable[..., Any],
    app_context: AppContext,
    plugin_name: Optional[str] = None,
) -> None:
    """
    Registers a data provider handler for a WebSocket topic.

    Args:
        topic (str): The topic name (e.g. 'server-status').
        handler (Callable): Async or sync function to handle requests for this topic.
        app_context (AppContext): Application context.
        plugin_name (Optional[str]): Name of registering plugin.

    Returns:
        Dict[str, Any]: Standard operation result.
    """
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
