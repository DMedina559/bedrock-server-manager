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
