# Calling the plugin API in 4.0

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

Use domain names such as `server`, `settings`, and `websocket`. Flat calls such as
`self.api.start_server(...)` and plural aliases such as `self.api.servers` are
removed. See [Available APIs](../../plugins/plugin_apis.md) for request fields,
response fields, and available operations. Import request models from
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

Player summaries require `player_count == len(players)`. Player scan counts obey
`saved <= unique <= discovered`. Contradictory API output fails validation rather
than reaching a plugin as a successful result.

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

Functions and context managers use `self.api.runtime`:

```python
task_id = await self.api.runtime.run_task(collect_stats, username="admin")
await self.api.runtime.register_data_provider("my-plugin:stats", provide_stats)
async with self.api.runtime.server_lifecycle_manager(
    server_name="example", stop_before=True, start_after=True
):
    await perform_operation()
```

Await server start, stop, and restart directly. Use background tasks for operations
whose progress must outlive an HTTP request. See [Background tasks](task_manager.md).
Use `get_plugin_setting` and `set_plugin_setting` for persistent plugin settings;
see [Plugin settings](settings.md).

## Operation context

Read the current callback and operation without changing callback signatures:

```python
from bedrock_server_manager import app_event
from bedrock_server_manager.operations import OperationResultQuery

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

Existing 4.0 callbacks keep their signatures. Opt into typed hooks with
`events.listen_typed` or `events.hook`, and immutable notification data with
`events.observe`. Discover contracts through `events.catalog`/`describe`, inspect
owned listeners through `events.subscriptions`, and manage temporary registrations
with `with` or `async with events.subscription(...)`. Filters and ordering are also
optional additions to existing listeners and decorators. Namespaced custom work
can use `with api.operations.scope("plugin_name:operation")`.

See [typed event access, filtering, and lifecycle cleanup](custom_events.md#opt-in-typed-hooks-and-observers)
for complete examples, visibility rules, deadlines, and compatibility guarantees.


### Backup component settings

Use the shared validated type instead of copying component names into a plugin:

```python
from pydantic import BaseModel, Field
from bedrock_server_manager.backups.contents import BackupComponents, DEFAULT_COMPONENTS

class PluginSettings(BaseModel):
    components: BackupComponents = Field(default_factory=lambda: list(DEFAULT_COMPONENTS))
```

`BackupComponents` rejects empty lists, duplicates and unsupported names. Its JSON Schema carries labels and defaults for checkbox editors. The same type is used by backup creation requests and global settings. `BackupContentSelection` provides a standalone Pydantic model with `mode` and `components` for validating selected-content preferences. Full-directory creation uses `mode="full"`; `server_directory` is only an archive/restore component.
