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

## Events

API before-events include a typed `request`. After-events also include a typed
`result`. Existing top-level request fields, such as `server_name`, remain
available. Use attributes on the models rather than dictionary methods.

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
