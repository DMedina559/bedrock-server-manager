"""Nonserializable integration capabilities, separate from the data API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from ..error import BSMError, UserInputError

if TYPE_CHECKING:
    from ..context import AppContext
logger = logging.getLogger(__name__)


async def run_task(
    target_function: Callable,
    *args: Any,
    app_context: AppContext,
    username: Optional[str] = None,
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
    # Safely get the name, unwrapping functools.partial if necessary
    actual_func = getattr(target_function, "func", target_function)
    task_name = getattr(actual_func, "__name__", str(target_function))

    logger.debug(f"API: Running task in background: {task_name}")

    return await app_context.task_manager.run_task(
        target_function, username, *args, **kwargs
    )


@asynccontextmanager
async def server_lifecycle_manager(
    server_name: str,
    stop_before: bool,
    app_context: AppContext,
    start_after: bool = True,
    restart_on_success_only: bool = False,
):
    """A context manager to safely stop and restart a server for an operation."""
    from ..api.models import StartServerRequest, StopServerRequest
    from ..api.server import start_server, stop_server

    server = app_context.get_server(server_name)
    was_running = False
    operation_succeeded = True

    # If the operation doesn't require a server stop, just yield and exit.
    if not stop_before:
        logger.debug(
            f"Context Mgr: Stop/Start not flagged for '{server_name}'. Skipping."
        )
        yield
        return

    try:
        # --- PRE-OPERATION: STOP SERVER ---

        if await server.is_running():
            logger.info(f"Context Mgr: Server '{server_name}' is running. Stopping...")
            await stop_server(
                StopServerRequest(server_name=server_name), app_context=app_context
            )
            was_running = True
            logger.info(f"Context Mgr: Server '{server_name}' stopped.")
        else:
            logger.debug(
                f"Context Mgr: Server '{server_name}' is not running. No stop needed."
            )

        # Yield control to the wrapped code block.
        yield

    except Exception:
        # If an error occurs in the `with` block, record it and re-raise.
        operation_succeeded = False
        logger.error(
            f"Context Mgr: Exception occurred during managed operation for '{server_name}'.",
            exc_info=True,
        )
        raise
    finally:
        # --- POST-OPERATION: RESTART SERVER ---
        # Only restart if the server was running initially and `start_after` is true.
        if was_running and start_after:
            should_restart = True
            # If `restart_on_success_only` is set, check if the operation failed.
            if restart_on_success_only and not operation_succeeded:
                should_restart = False
                logger.warning(
                    f"Context Mgr: Operation for '{server_name}' failed. Skipping restart as requested."
                )

            if should_restart:
                logger.info(f"Context Mgr: Restarting server '{server_name}'...")
                try:
                    # Use the API function to ensure detached mode and proper handling.
                    await start_server(
                        StartServerRequest(server_name=str(server_name)),
                        app_context=app_context,
                    )
                    logger.info(
                        f"Context Mgr: Server '{server_name}' restart initiated."
                    )
                except BSMError as e:
                    logger.error(
                        f"Context Mgr: FAILED to restart '{server_name}': {e}",
                        exc_info=True,
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
) -> Dict[str, Any]:
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
        return {
            "status": "success",
            "message": f"Data provider registered for topic '{topic}'",
        }
    except Exception as e:
        logger.error(
            f"Failed to register data provider for topic '{topic}': {e}", exc_info=True
        )
        raise
