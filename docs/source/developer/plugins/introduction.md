# Write a plugin

Plugins extend BSM through `PluginBase`, typed API capabilities and declared events. Start with [typed contracts](contracts.md), then consult the generated [API](../../plugins/plugin_apis.md) and [event](../../plugins/plugin_events.md) references for exact names and payloads.

## Minimal plugin

Save this as `my_plugin.py` in the configured user plugin directory:

```python
from bedrock_server_manager import PluginBase, app_event


class MyPlugin(PluginBase):
    """Log successful server starts."""

    version = "1.0.0"
    description = "Log successful server starts."

    @app_event("on_load")
    async def loaded(self, **kwargs):
        self.logger.info("Plugin loaded")

    @app_event("after_server_start")
    async def started(self, server_name, result, **kwargs):
        if result.status == "success":
            self.logger.info("Server %s started", server_name)
```

Discover and enable the plugin through management, then check its load log. Internal identity comes from the file/package name; `name` changes the display name. Define a `version`, and optionally `author`, `description`, `dependencies` and `optional_dependencies`.

For a package, put the main subclass in—or expose it from—`my_plugin/__init__.py`. Additional modules can live beside it. Dependencies refer to plugin identities, not arbitrary Python packages; install Python dependencies into BSM's environment separately.

## Standardized decorators and declarative attributes

Import decorators and `PluginBase` directly from `bedrock_server_manager`. BSM automatically discovers and registers these extensions when your plugin loads, and cleans them up on unload:

| Extension | How to declare | Purpose |
|---|---|---|
| Event listeners | `@app_event("event_name")` | Listen to lifecycle, before/after operation, or custom events |
| Periodic background loops | `@task_loop(interval=60)` | Run an async or sync method repeatedly while the plugin is loaded |
| Scheduled server tasks | `@scheduled_task(...)` | Register an async handler in the server scheduler (`<plugin_name>:<task>`) |
| Scheduled API tasks | `scheduled_apis = [...]` | Expose existing `@api_method` APIs or dotted API paths in the scheduler |
| Diagnostic providers | `@diagnostic_provider(...)` | Contribute bounded numeric/boolean telemetry to `plugin:<plugin_name>:<name>` |
| WebSocket data providers | `@data_provider("topic")` / `@websocket_provider("topic")` | Handle WebSocket `request` messages for `<plugin_name>:<topic>` |
| FastAPI routes | `router = APIRouter(...)` or `routers = [...]` | Mount custom authenticated HTTP/UI routes on the web application |
| Static asset mounts | `static_mounts = [(prefix, path, name)]` | Mount static directories under the plugin web namespace |
| HTTP permissions | `http_permissions = [(perm, description, roles)]` | Register custom `plugin:<plugin_name>:<perm>` HTTP scopes |
| Typed settings | `settings_model`, `global_settings_model`, `server_settings_model` | Validate plugin, global, and per-server settings and generate web forms |

Imperative registration methods (`get_fastapi_routers()`, `get_static_mounts()`, `api.runtime.register_scheduled_task()`, `api.runtime.register_diagnostic_provider()`, `api.runtime.register_data_provider()`, `api.runtime.register_http_permission()`) and unscoped `self.api.<method>` calls remain supported for backward compatibility, but log deprecation warnings and will be removed in a future release.

## Call typed capabilities

Use domain-scoped namespaces on `self.api` (for example `self.api.server`, `self.api.backup_restore`, `self.api.settings`) with declared request models or supported mappings. Results are Pydantic models; inspect their fields and use `model_dump(mode="json")` when serialization is needed. The bridge supplies caller identity; do not pass a caller plugin name or AppContext.

Use `PluginBase` settings helpers and managed runtime capabilities instead of importing internal servers, database sessions or application context. Narrow capabilities preserve ownership and cleanup boundaries. Await direct operations when their result is needed; see [managed tasks](task_manager.md) for work that belongs in the background.

## Handle events

Use `@app_event` for known events and read the event reference's typed request/result fields. Before-operation hooks can cancel an operation; notifications and observers do not veto it. Avoid recursively invoking the same operation from its own before-hook.

Prefer asynchronous handlers. Supported synchronous handlers run in bounded workers and must cooperate with cancellation; a timeout does not forcibly stop a Python thread. Keep hooks short and move long notification work to the supported queued or managed-task facilities.

For custom declarations, priorities, delivery limits, waits and diagnostics, use the [event guide](custom_events.md). Declare custom events in your plugin's owned namespace rather than emitting another plugin's undeclared events.

## Own and release resources

Declare routes, listeners, scheduled tasks, diagnostic providers, and WebSocket data providers through `PluginBase` attributes and decorators, or use `self.api.runtime` and `self.api.events` when dynamic registration is required. Stop producers and release external resources during unload. Reload can be blocked while an old generation still has outstanding synchronous work.

Additional guides cover [plugin settings](settings.md), [scheduled tasks](scheduled_tasks.md), [FastAPI routes](fastapi_endpoints.md), [background tasks](task_manager.md), and [native JSON UI](native_json_ui.md). Authenticate custom routes explicitly and validate their requests with Pydantic models.
