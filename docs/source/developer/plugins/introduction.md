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

## Call typed capabilities

Use `self.api` with declared request models or supported mappings. Results are Pydantic models; inspect their fields and use `model_dump(mode="json")` when serialization is needed. The bridge supplies caller identity; do not pass a caller plugin name or AppContext.

Use `PluginBase` settings helpers and managed runtime capabilities instead of importing internal servers, database sessions or application context. Narrow capabilities preserve ownership and cleanup boundaries. Await direct operations when their result is needed; see [managed tasks](task_manager.md) for work that belongs in the background.

## Handle events

Use `@app_event` for known events and read the event reference's typed request/result fields. Before-operation hooks can cancel an operation; notifications and observers do not veto it. Avoid recursively invoking the same operation from its own before-hook.

Prefer asynchronous handlers. Supported synchronous handlers run in bounded workers and must cooperate with cancellation; a timeout does not forcibly stop a Python thread. Keep hooks short and move long notification work to the supported queued or managed-task facilities.

For custom declarations, priorities, delivery limits, waits and diagnostics, use the [event guide](custom_events.md). Declare custom events in your plugin's owned namespace rather than emitting another plugin's undeclared events.

## Own and release resources

Register routes, listeners, waits, tasks and data providers through supported capabilities. Stop producers and release external resources during unload. Reload can be blocked while an old generation still has outstanding synchronous work.

Additional guides cover [settings](settings.md), [FastAPI routes](fastapi_endpoints.md) and [native JSON UI](native_json_ui.md). Authenticate custom routes explicitly and validate their requests with Pydantic models.
