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

Declare the capabilities used by your plugin on its `PluginBase` subclass:

```python
class MyPlugin(PluginBase):
    version = "1.0.0"
    permissions = ["server:command", "maintenance:backups"]
```

Declarations accept lists, tuples, sets, or frozensets of nonempty scope strings.
Omitting `permissions` or setting it to `None` preserves legacy access to scoped
APIs for older plugins. An explicit collection opts into capability enforcement:
`permissions = []` grants no scoped capabilities, and a nonempty collection grants
only its listed scopes. BSM validates explicit declarations and snapshots the
legacy mode or immutable scope set when a plugin loads. Changing the declaration
while the plugin is running does not change its authority; reload the plugin
to apply declaration changes. Unknown scope names produce a warning and do not
match another capability. Invalid declaration types prevent that plugin from
loading without interrupting discovery of healthy plugins.

These declarations describe access through BSM's supported plugin APIs. Plugins
execute as trusted, in-process Python code and can import Python modules; install
only trusted plugins. Declaring a capability does not create an HTTP account
permission, and account permissions do not grant plugin capabilities.

| Scope | Purpose |
|---|---|
| `path:servers` | Access Bedrock server installation directories |
| `path:backups` | Access backup archives and snapshot storage |
| `path:content` | Access content import directories (worlds and packs) |
| `path:downloads` | Access cached server download archives |
| `path:themes` | Access custom Web UI themes |
| `server:lifecycle` | Start, stop, and restart game servers |
| `server:command` | Send interactive console commands to running servers |
| `addon:manage` | Enable, disable, import, or reorder server addons |
| `server:allowlist` | Add or remove players from the server allowlist |
| `backup:create` | Create server backups and snapshots |
| `backup:restore` | Restore server snapshots and recovery data |
| `maintenance:backups` | Prune server backups using configured retention |
| `backup:manage` | Manage, verify, drill, and pin server snapshots |
| `server:ban` | Add or remove server player bans |
| `server:install` | Install new servers and update server software binaries |
| `maintenance:downloads` | Prune the configured server download cache |
| `server:permissions` | Modify Minecraft player operator permissions (permissions.json) |
| `server:properties` | Modify server.properties configuration |
| `websocket:send` | Broadcast and send messages to WebSocket clients |
| `world:manage` | Import or export Minecraft server worlds |
| `world:reset` | Reset and regenerate server worlds |

Pruning requires `maintenance:backups` or `maintenance:downloads` respectively.
`backup:manage` covers snapshot verification, recovery drills, and pinning instead.
Plugin download pruning is confined to the configured download cache or a
subdirectory; an explicit path outside that tree, including a symlink resolving
outside it, is rejected. `path:downloads` permits retrieving the configured path
but does not independently permit a prune operation.

The root `paths` setting and `paths.plugins` are permanently restricted.
`api.runtime.server_lifecycle_manager()` requires `server:lifecycle`, including
when called with positional options. A composite API's documented capability
covers its internal lifecycle work, such as stopping a server during restore.

Direct and scheduled API calls use the same permission mode: omitted/`None`
declarations retain legacy access, while explicit collections are enforced.
Plugin-owned `scheduled_apis` and `api.runtime.register_api_task()` jobs run through the owning
plugin's bridge, including when a registered function is supplied as a callable.
Internal APIs cannot be scheduled by plugins, including legacy plugins.
Custom plugin task callbacks must not request internal `app_context`. Core-owned schedules retain core authority.
API and runtime handles belong to one plugin load generation: retained handles
stop working after unload and remain invalid when the same plugin name reloads.

`websocket:send` covers broadcasting, publishing WebSocket events, and sending
messages to users or clients. Provider removal requires ownership: a plugin can
remove its own provider without a capability, but cannot remove core providers or
another plugin's providers. Registration also rejects replacing a provider owned
by core or another plugin. Registration and provider cleanup use the injected
plugin identifier, not its display name.

#### APIs without a required capability declaration

These methods retain their existing availability. The bridge still injects
identity and enforces its lifetime. Owner-scoped settings operations retain their
namespace checks; global path settings additionally check the relevant `path:*`
capability. The compatibility custom-value/player update APIs listed below
remain available without an additional capability.

| Domain | Methods |
|---|---|
| addon | `addon.list_available_addons`, `addon.list_installed_addons` |
| allowlist | `allowlist.get_allowlist` |
| application | `application.get_all_servers_data`, `application.get_system_and_app_info`, `application.list_available_worlds` |
| backup_restore | `backup_restore.can_reuse_server_backup`, `backup_restore.download_backup_recovery_report`, `backup_restore.get_backup_health`, `backup_restore.get_restore_recovery`, `backup_restore.inspect_server_backup`, `backup_restore.list_backup_files`, `backup_restore.list_server_snapshots`, `backup_restore.plan_server_restore` |
| ban | `ban.get_server_bans` |
| diagnostics | `diagnostics.compare_diagnostic_snapshots`, `diagnostics.get_application_diagnostics`, `diagnostics.get_diagnostic_activity`, `diagnostics.get_diagnostic_history`, `diagnostics.get_diagnostic_report`, `diagnostics.get_diagnostic_runs`, `diagnostics.get_diagnostic_trace` |
| permissions | `permissions.get_permissions` |
| player | `player.add_players_manually`, `player.get_all_known_players`, `player.scan_and_update_player_db` |
| plugins | `plugins.get_plugin_setting`, `plugins.get_plugin_statuses`, `plugins.set_plugin_setting` |
| properties | `properties.get_properties`, `properties.get_raw_properties`, `properties.validate_property_value` |
| scheduler | `scheduler.list_schedules` |
| server | `server.get_all_settings`, `server.get_setting`, `server.get_summary`, `server.get_valid_names`, `server.set_custom_value` |
| settings | `settings.get_all_global_settings`, `settings.get_global_setting`, `settings.set_custom_global_setting` |
| system | `system.get_application_health`, `system.get_application_metrics`, `system.get_bedrock_process_info`, `system.get_server_running_status` |
| websocket | `websocket.websocket_unregister_data_provider` |
| world | `world.get_world_name` |

Reading and writing the caller's private plugin files or the shared public plugin
directory uses the file scope (`private` or `public`) and requires no `path:*`
declaration. Plugin, global, and server **settings scopes** describe where the
plugin's own settings are stored; they are separate from capability permissions.

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
