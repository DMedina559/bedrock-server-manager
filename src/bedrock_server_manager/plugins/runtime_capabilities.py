"""Nonserializable integration capabilities, separate from the data API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from ..error import UserInputError
from ..logging import log_operation_error

if TYPE_CHECKING:
    from ..context import AppContext
    from .files import PluginFileFormat, PluginFileScope

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
    """Register an owner-scoped WebSocket topic provider (deprecated; prefer @data_provider)."""
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

    logger.warning(
        "Plugin '%s' used deprecated 'api.runtime.register_data_provider()'; use the '@data_provider' decorator instead. 'register_data_provider()' will be removed in a future version.",
        plugin_name or "unknown",
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
    """Register asynchronous numeric metadata for this plugin's diagnostic section (deprecated; prefer @diagnostic_provider)."""
    if not plugin_name:
        raise UserInputError("Plugin diagnostics require an explicit owner")
    logger.warning(
        "Plugin '%s' used deprecated 'api.runtime.register_diagnostic_provider()'; use the '@diagnostic_provider' decorator instead. 'register_diagnostic_provider()' will be removed in a future version.",
        plugin_name,
    )
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


async def read_plugin_file(
    filename: str,
    *,
    scope: PluginFileScope = "private",
    format: PluginFileFormat = "json",
    app_context: AppContext,
    plugin_name: str,
):
    """Read a file from this plugin's private directory or the shared public plugin directory."""
    from ..utils.threads import run_in_thread
    from .files import read_plugin_content

    return await run_in_thread(
        read_plugin_content,
        app_context.config_dir,
        plugin_name,
        filename,
        scope=scope,
        format=format,
    )


async def write_plugin_file(
    filename: str,
    value: Any,
    *,
    scope: PluginFileScope = "private",
    format: PluginFileFormat = "json",
    app_context: AppContext,
    plugin_name: str,
) -> None:
    """Atomically write a file inside this plugin's private directory or the shared public plugin directory."""
    from ..utils.threads import run_in_thread
    from .files import write_plugin_content

    await run_in_thread(
        write_plugin_content,
        app_context.config_dir,
        plugin_name,
        filename,
        value,
        scope=scope,
        format=format,
    )


async def get_plugin_data_path(
    filename: str = "",
    *,
    scope: PluginFileScope = "private",
    app_context: AppContext,
    plugin_name: str,
):
    """Return a validated path inside this plugin's private directory or the shared public plugin directory."""
    from ..utils.threads import run_in_thread
    from .files import plugin_path

    def _resolve():
        target = plugin_path(
            app_context.config_dir,
            plugin_name,
            filename,
            scope=scope,
        )
        base = plugin_path(
            app_context.config_dir,
            plugin_name,
            scope=scope,
        )
        base.mkdir(parents=True, exist_ok=True)
        return target

    return await run_in_thread(_resolve)


async def get_system_path(
    scope: str,
    *,
    app_context: AppContext,
    plugin_name: str,
) -> Path:
    """Return a validated host storage path for a granted path scope."""
    from .scopes import GRANTABLE_PATH_SCOPES

    if scope not in GRANTABLE_PATH_SCOPES:
        raise PermissionError(f"Scope '{scope}' is not a grantable system path.")

    from .scopes import require_plugin_permission

    require_plugin_permission(app_context, plugin_name, f"path:{scope}")

    raw_path = app_context.settings.get(GRANTABLE_PATH_SCOPES[scope])
    if not raw_path:
        raise FileNotFoundError(
            f"Host filesystem path for scope '{scope}' is not configured."
        )

    return Path(raw_path).expanduser().resolve()


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
    description: str = "",
):
    """Register an async ``plugin_name:task`` handler accepting server_name and options.

    Deprecated for plugin methods; prefer the ``@scheduled_task`` decorator or
    ``api.runtime.register_api_task``.
    """
    logger.warning(
        "Plugin '%s' used deprecated 'api.runtime.register_scheduled_task()'; use the '@scheduled_task' decorator or 'api.runtime.register_api_task()' instead. 'register_scheduled_task()' will be removed in a future version.",
        plugin_name,
    )
    owner = f"plugin:{plugin_name}"
    bus = app_context.events
    return app_context.scheduler.tasks.register(
        name,
        handler,
        owner=owner,
        generation=bus.owner_generation(owner),
        options_model=options_model,
        timeout_seconds=timeout_seconds,
        requires_server_lock=requires_server_lock,
        with_context=with_context,
        description=description,
    )


def register_api_task(
    name: str,
    api_method: Callable[..., Any] | str,
    *,
    app_context: AppContext,
    plugin_name: str,
    options_model=None,
    default_options: dict[str, Any] | None = None,
    slot_field: str | None = None,
    timeout_seconds: float = 300,
    requires_server_lock: bool = True,
    description: str = "",
):
    """Register an API method or callable to run as a scheduled plugin task."""
    owner = f"plugin:{plugin_name}"
    bus = app_context.events
    return app_context.scheduler.tasks.register_api_task(
        name,
        api_method,
        owner=owner,
        generation=bus.owner_generation(owner),
        options_model=options_model,
        default_options=default_options,
        slot_field=slot_field,
        timeout_seconds=timeout_seconds,
        requires_server_lock=requires_server_lock,
        description=description,
    )


def register_http_permission(
    permission: str,
    description: str,
    roles: list[str],
    *,
    server_scoped: bool = False,
    app_context: AppContext,
    plugin_name: str,
) -> None:
    """Register a namespaced HTTP capability with explicit role grants (deprecated; prefer http_permissions attribute)."""
    logger.warning(
        "Plugin '%s' used deprecated 'api.runtime.register_http_permission()'; declare 'http_permissions' on the plugin class/instance instead. 'register_http_permission()' will be removed in a future version.",
        plugin_name,
    )
    if not permission.startswith("plugin:"):
        permission = f"plugin:{plugin_name}:{permission}"
    app_context.plugin_manager.access_policy.register(
        plugin_name, permission, description, roles, server_scoped=server_scoped
    )
