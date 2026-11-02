# Calling the plugin API

Use `self.api` to access supported operations. Each data operation accepts one
request model or mapping and returns a Pydantic response model.

```python
from bedrock_server_manager.api.models import StartServerRequest

result = await self.api.server.start(StartServerRequest(server_name="example"))
self.logger.info(result.message)
```

The same call can use a mapping:

```python
result = await self.api.server.start({"server_name": "example"})
```

Use domain names such as `server`, `settings`, and `websocket` (unscoped calls
like `self.api.start(...)` are deprecated and log a warning). See
[Available APIs](../../plugins/plugin_apis.md) for request fields, response
fields, and available operations. Import request models from
`bedrock_server_manager.api.models`.

Read response attributes directly. Use `result.model_dump(mode="json")` when you
need JSON data. Do not pass `app_context` or caller `plugin_name`; the bridge
supplies them. Plugin-target operations use `target_plugin_name` instead.

## Validation and failures

Requests reject unknown fields and invalid types. JSON data cannot contain
objects, NaN, or infinity. Catch Pydantic `ValidationError` for invalid requests
and application exceptions for failed operations. Plugin cancellation raises
`APICancelledError`.

An already-running start returns `outcome="already_running"`; an already-stopped
stop returns `outcome="already_stopped"`. These are successful results. Operations
that return `status="skipped"` also return normally; inspect the response to decide
whether your plugin should continue.

`status="partial"` also returns normally: some work completed and some failed.
Inspect the typed details instead of treating every returned response as complete
success. Backup/restore components have `completed`, `skipped`, or `failed`
outcomes. Failed components include a structured error; completed components can
include their archive path. Cleanup results distinguish deleted and retained paths
from failed deletions. WebSocket delivery results count sent, unavailable, and
failed recipients, so an absent connection does not imply delivery.

```python
from bedrock_server_manager.api.models import BackupAllRequest
from bedrock_server_manager.error import IncompleteOperationError

try:
    result = await self.api.backup_restore.backup_all(
        BackupAllRequest(server_name="example")
    )
except IncompleteOperationError as error:
    # Validated results may describe work completed before the failure.
    self.logger.warning("Backup incomplete: %s", error.result.model_dump(mode="json"))
    raise
else:
    for component, item in result.details.components.items():
        self.logger.info("%s: %s", component, item.outcome)
```

Do not convert infrastructure failures into missing resources or negative states.
Release lookup, service-manager, filesystem permission, and migration failures
propagate. Malformed existing allowlist and permission files are preserved for
repair. Recovery failures retain the primary exception when the main operation
also failed. Python exceptions are classified into stable codes and safe messages
at HTTP, WebSocket, and background-task boundaries.

## Capability permissions

Operations that modify server lifecycle, state, configurations, or storage require explicit capability permissions. Declare these permissions on your `PluginBase` subclass:

```python
from bedrock_server_manager import PluginBase

class MyPlugin(PluginBase):
    version = "1.0.0"
    permissions = ["server:lifecycle", "server:command"]
```

If a plugin attempts to call a protected API method without declaring the required permission, BSM raises `PermissionError`:

```python
try:
    await self.api.server.start(StartServerRequest(server_name="example"))
except PermissionError as error:
    self.logger.error("Missing required capability: %s", error)
```

At load time, `PluginManager` checks the plugin's declared permissions and logs a warning if an unrecognized permission scope is declared. See [Write a plugin](introduction.md#capability-permissions-permissions--) for the complete list of valid capability scopes.

## Events

API before-events include a typed `request`. After-events also include a typed
`result`. Existing top-level request fields, such as `server_name`, remain
available. Use attributes on the models rather than dictionary methods. Event
request and result models are copies; mutating them does not change the original
operation. After-events can include partial or skipped results, so inspect the
result status before assuming work completed.

```python
from bedrock_server_manager import app_event
from bedrock_server_manager.api.models import StartServerRequest, StartServerResponse

@app_event("after_server_start")
async def server_started(self, request: StartServerRequest,
                         result: StartServerResponse, **kwargs):
    self.logger.info("%s: %s", request.server_name, result.outcome)
```

Before-events can cancel through the separate `event` object. Custom events use
JSON values. See [Custom events](custom_events.md) and
[Available events](../../plugins/plugin_events.md).

## Runtime capabilities

Runtime helpers, plugin-owned files, dynamic API task registration, and lifecycle context managers use `self.api.runtime`:

```python
# Managed background task
task_id = await self.api.runtime.run_task(collect_stats, username="admin")

# Dynamic API scheduled task registration
self.api.runtime.register_api_task("prune", "backup_restore.prune_old_backups")

# Scoped plugin file I/O (private to <config_dir>/plugins/<plugin_name>/ or shared in <config_dir>/plugins/public/)
await self.api.runtime.write_plugin_file("state.json", {"ready": True}, scope="private", format="json")
state = await self.api.runtime.read_plugin_file("state.json", scope="private", format="json")
data_dir = await self.api.runtime.get_plugin_data_path(scope="private")

# Temporary server stop/start wrapper
async with self.api.runtime.server_lifecycle_manager(
    server_name="example", stop_before=True, start_after=True
):
    await perform_operation()
```

Declare WebSocket data providers, diagnostic providers, and custom scheduled task methods with the `@data_provider` / `@websocket_provider`, `@diagnostic_provider`, and `@scheduled_task` decorators on `PluginBase`. Await server start, stop, and restart directly. Use background tasks for operations whose progress must outlive an HTTP request. See [Scheduled tasks](scheduled_tasks.md) and [Background tasks](task_manager.md). Use `get_plugin_setting` and `set_plugin_setting` for persistent plugin settings, and `read_plugin_file` / `write_plugin_file` / `get_plugin_data_path` for plugin-owned files on disk; see [Plugin settings and storage](settings.md).

## Operation context

Read the current callback and operation without changing callback signatures:

```python
from bedrock_server_manager import OperationResultQuery, app_event

@app_event("before_server_start", priority=-10)
async def inspect_start(self, server_name, **kwargs):
    event_context = self.api.events.current()
    operation = self.api.operations.current()
    sequence = self.api.operations.sequence()
    completed = self.api.operations.results(OperationResultQuery(
        name="backup.create",
        server_name=server_name,
        status="finished",
        outcome="completed",
    ))
    required = {"world", "server.properties", "allowlist.json", "permissions.json"}
    protected = any(required.issubset(item.scope) for item in completed)
    self.logger.debug("Sequence %s has a complete backup: %s",
                      sequence.sequence_id, protected)
```

`events.current()` returns event ID, name, parent-event ID, correlation ID,
source, and associated operation/sequence IDs. It excludes payloads and returns
`None` outside a callback. `operations.current()` and `operations.sequence()`
return `None` outside an operation; `operations.results()` returns an empty tuple.

Operation snapshots include IDs, ancestry links, server, source/owner, purpose,
execution status, domain outcome, component scope, and timing. Snapshots and result
tuples are immutable. Results are restricted to the current sequence, oldest first,
and may be filtered by name, server, status, outcome, or purpose. The query `limit`
defaults to 200. `sequence.results_truncated` reports sequence retention loss;
missing or insufficient evidence must never be treated as successful work.

A `finished` operation can still have a partial or skipped domain outcome.
Successful update results distinguish `updated` from `up_to_date`. A backup
operation ID identifies its logical batch; use the backup inventory API for files.
For backups, require `outcome="completed"` and the necessary component scope.
A pre-update backup has purpose `pre_update`; a standalone pre-start backup has
purpose `pre_start`. Its files represent the server at that point in the sequence.
Do not use event delivery status or recent-backup timestamps as proof.

Plugins cannot register core completion records, mutate the live sequence, or
inspect unrelated sequences through this capability. Capabilities retained after
unload/reload fail rather than attaching to a replacement plugin generation.
Sequences are in-memory and end when the root call exits. Detached background
work starts an independent sequence when it invokes a tracked operation.

### Additional event capabilities

Opt into typed hooks with `events.listen_typed` or `events.hook`, and immutable
notification data with `events.observe`. Discover contracts through
`events.catalog`/`describe`, inspect owned listeners through
`events.subscriptions`, and manage temporary registrations with `with` or
`async with events.subscription(...)`. See
[typed event access, filtering, and lifecycle cleanup](custom_events.md#opt-in-typed-hooks-and-observers)
for complete examples, visibility rules, and deadlines.


### Backups, snapshots, and component settings

Prefer the unified `.bsmbackup` snapshot APIs on `self.api.backup_restore` (`create_server_backup`, `list_server_snapshots`, `plan_server_restore`, and `restore_server_snapshot`) when building new backup or restore integrations. The component-specific convenience methods (`backup_all`, `backup_world`, `backup_config_files`, `restore_world`, `restore_config_file`) remain supported and operate on legacy or component archives.

Use the shared validated `BackupComponents` type instead of copying component names into a plugin:

```python
from pydantic import BaseModel, Field
from bedrock_server_manager.backups.contents import BackupComponents, DEFAULT_COMPONENTS

class PluginSettings(BaseModel):
    components: BackupComponents = Field(default_factory=lambda: list(DEFAULT_COMPONENTS))
```

`BackupComponents` rejects empty lists, duplicates and unsupported names. Its JSON Schema carries labels and defaults for checkbox editors. The same type is used by backup creation requests and global settings. `BackupContentSelection` provides a standalone Pydantic model with `mode` and `components` for validating selected-content preferences. Full-directory creation uses `mode="full"`; `server_directory` is only an archive/restore component.
