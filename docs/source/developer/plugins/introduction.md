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

Discover and enable the plugin through management, then check its load log. Internal identity (`<plugin_name>`) comes from the Python file stem (`my_plugin.py` → `my_plugin`) or package directory name (`my_plugin/__init__.py` → `my_plugin`).

### Discovery and naming rules

- **Required metadata:** Your `PluginBase` subclass must define a non-empty `version` (other than `"N/A"`). Put the human-readable description in the class docstring (or `description = "..."`), and optionally define `author`, `dependencies`, and `optional_dependencies`.
- **Allowed plugin names:** Files or directories starting with `_` or `.` are ignored during discovery. The names `public`, `shared`, and `private` are reserved by the plugin file storage system and are never discovered as plugins. If your plugin declares `global_settings_model` or `server_settings_model`, `<plugin_name>` must also be a single safe namespace segment (no `.` or `__`).
- **Package vs. single-file layout:** Single-file plugins (`<data_dir>/plugins/my_plugin.py`) work for most hooks, tasks, and API routes. If your plugin mounts local static web assets via `static_mounts`, use a package directory (`<data_dir>/plugins/my_plugin/__init__.py`) so its assets reside inside `<data_dir>/plugins/my_plugin/...`.
- **Dependencies:** `dependencies` and `optional_dependencies` list other BSM plugin identities (their file/package stems), not PyPI package names. Install third-party Python packages into BSM's Python environment separately.

## Standardized decorators and declarative attributes

Import decorators and `PluginBase` directly from `bedrock_server_manager`. BSM automatically discovers and registers these extensions when your plugin loads, and cleans them up on unload:

| Extension | How to declare | Purpose |
|---|---|---|
| Event listeners | `@app_event("event_name")` | Listen to lifecycle, before/after operation, or custom events |
| Periodic background loops | `@task_loop(interval=60)` | Run an async or sync method repeatedly while the plugin is loaded |
| Scheduled server tasks | `@scheduled_task(...)` | Register an async handler in the server scheduler (`<plugin_name>:<task>`) |
| Scheduled API tasks | `scheduled_apis = [...]` | Expose existing `@api_method` APIs or dotted API paths in the scheduler |
| Diagnostic providers | `@diagnostic_provider(...)` | Contribute bounded async numeric/boolean telemetry to `plugin:<plugin_name>:<name>` |
| WebSocket data providers | `@data_provider("topic")` / `@websocket_provider("topic")` | Handle WebSocket `request` messages for `topic` (use `"<plugin_name>:..."` by convention) |
| FastAPI routes | `router = APIRouter(...)` or `routers = [...]` | Mount custom authenticated HTTP/UI routes on the web application |
| Static asset mounts | `static_mounts = [(prefix, path, name)]` | Mount static directories under the plugin web namespace |
| Capability permissions | `permissions = ["path:servers", ...]` | Declare required filesystem and system storage capabilities |
| HTTP permissions | `http_permissions = [(perm, description, roles)]` | Register custom `plugin:<plugin_name>:<perm>` HTTP scopes |
| Typed settings | `settings_model`, `global_settings_model`, `server_settings_model` | Validate plugin, global, and per-server settings and generate web forms |
| Scoped plugin files | `self.api.runtime.read_plugin_file` / `write_plugin_file` / `get_plugin_data_path` | Read and write private (`<config_dir>/plugins/<plugin_name>/`) or shared (`<config_dir>/plugins/public/`) files |

Imperative registration methods (`get_fastapi_routers()`, `get_static_mounts()`, `api.runtime.register_scheduled_task()`, `api.runtime.register_diagnostic_provider()`, `api.runtime.register_data_provider()`, `api.runtime.register_http_permission()`) and unscoped `self.api.<method>` calls remain supported for backward compatibility, but log deprecation warnings and will be removed in a future release.

## Diagnostic and WebSocket data providers

### Diagnostic providers (`@diagnostic_provider`)

Decorate an `async def` method with `@diagnostic_provider("name")` (or `@diagnostic_provider` to use the method name) to expose live plugin telemetry in `/api/diagnostics/plugins` (`plugin:<plugin_name>:<name>`).

- Providers **must be asynchronous** (`async def`). Synchronous functions raise a `ValueError` during registration.
- Return a flat mapping (`dict[str, int | float | bool]`) or `PluginValues(health=..., values={...}, units={...}, labels={...})` with at most 32 keys. Only booleans and finite numbers (`int`, `float`) are accepted; strings, nested objects, `None`, `NaN`, and `Infinity` are rejected so diagnostic snapshots cannot leak secrets or unbounded payloads.
- Provider `health` defaults to `"unknown"`; pass `health="ok"` or `health="degraded"` on `PluginValues` when the provider has health evidence. Optional `units` may use `"count"`, `"seconds"`, `"milliseconds"`, `"bytes"`, or `"percent"`, and optional `labels` are bounded to 80 characters.
- Plugins can also read typed diagnostics through `self.api.diagnostics.get_application_diagnostics({})`, `get_diagnostic_history({})`, and `get_diagnostic_report({})`.

```python
from bedrock_server_manager import PluginBase, diagnostic_provider
from bedrock_server_manager.diagnostics import PluginValues


class MyTelemetryPlugin(PluginBase):
    """Publish bounded plugin health metrics."""

    version = "1.0.0"

    @diagnostic_provider("queue_stats")
    async def queue_stats(self) -> PluginValues:
        return PluginValues(
            health="ok",
            values={
                "healthy": True,
                "pending_items": 4,
                "last_latency_ms": 12.5,
            },
            units={
                "pending_items": "count",
                "last_latency_ms": "milliseconds",
            },
        )
```

### WebSocket data providers (`@data_provider` / `@websocket_provider`)

Decorate an `async def` or synchronous method with `@data_provider("my_plugin:stats")` (aliased as `@websocket_provider`) to answer client `{"action": "request", "topic": "my_plugin:stats", "params": {...}}` frames over `/ws`.

- The `topic` string is registered verbatim in the WebSocket connection manager. Prefix custom topics with `<plugin_name>:` (for example, `"my_plugin:stats"`) so they do not collide with core topics or other plugins.
- The method receives keyword arguments matching the client's `params` dictionary and returns JSON-serializable data, which BSM sends back to the requesting client in a `{"type": "response", "topic": ..., "data": ...}` frame.

### Capability permissions (`permissions = [...]`)

Declare required system and server capability scopes on your `PluginBase` subclass. BSM enforces these scopes when plugins invoke sensitive `@api_method` APIs or access paths:

```python
class MyPlugin(PluginBase):
    version = "1.0.0"
    permissions = ["server:command", "server:lifecycle"]
```

| Scope | Description | Associated APIs |
|---|---|---|
| `path:servers` | Access server installation directories | `api.runtime.get_system_path("servers")`, `paths.servers` |
| `path:backups` | Access backup archives and snapshot storage | `api.runtime.get_system_path("backups")`, `paths.backups` |
| `path:content` | Access content import directories (worlds and packs) | `api.runtime.get_system_path("content")`, `paths.content` |
| `path:downloads` | Access cached server download archives | `api.runtime.get_system_path("downloads")`, `paths.downloads` |
| `path:themes` | Access custom Web UI themes | `api.runtime.get_system_path("themes")`, `paths.themes` |
| `server:command` | Send interactive console commands | `api.server.send_command` |
| `server:lifecycle` | Start, stop, and restart game servers | `api.server.start_server`, `stop_server`, `restart_server` |
| `server:properties` | Modify server.properties configuration | `api.properties.set_properties` |
| `server:permissions` | Modify Minecraft player operator permissions | `api.permissions.set_permissions` |
| `server:allowlist` | Add or remove players from the server allowlist | `api.allowlist.add_to_allowlist`, `remove_from_allowlist` |
| `server:ban` | Add or remove server player bans | `api.ban.add_server_ban`, `remove_server_ban` |
| `world:manage` | Import or export Minecraft server worlds | `api.world.import_world`, `export_world` |
| `addon:manage` | Enable, disable, import, or reorder server addons | `api.addon.enable_addon`, `disable_addon`, `import_addon`, `reorder_addons` |
| `backup:create` | Create server backups and snapshots | `api.backup_restore.backup_*`, `create_server_backup` |

> [!NOTE]
> The root `"paths"` configuration key and `"paths.plugins"` directory are permanently restricted and cannot be granted to any plugin.

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
