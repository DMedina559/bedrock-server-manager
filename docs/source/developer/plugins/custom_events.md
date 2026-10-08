# Custom events and cancellation

Use `@app_event` to listen to application events. See
[Available events](../../plugins/plugin_events.md) for event names and fields,
and [API contracts](contracts.md) for typed request and result handling.

## Cancelling an operation

Before-events include an `event` control object. Call `event.cancel(reason)` to
prevent the operation. Cancellation raises `APICancelledError` to the caller and
suppresses the corresponding after-event.

```python
from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.api.models import StartServerRequest

class MaintenancePlugin(PluginBase):
    version = "4.0.0"

    @app_event("before_server_start")
    async def before_start(self, request: StartServerRequest, event, **kwargs):
        if await self.get_plugin_setting("maintenance", default=False):
            event.cancel("Server maintenance is enabled.")
```

## Publishing a WebSocket event

Use JSON values for custom event data. Do not include runtime objects,
credentials, or application context.

```python
await self.api.websocket.websocket_publish_ws_event({
    "event_name": "my_plugin:refresh",
    "data": {"server_name": "example", "reason": "settings_changed"},
})
```

For topic data and live dashboards, use `self.api.websocket.broadcast` and
`self.api.runtime.register_data_provider`; see the
[plugin introduction](introduction.md) and [Native JSON UI](native_json_ui.md).
