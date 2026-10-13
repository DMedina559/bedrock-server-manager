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

## Application event subsystem

`AppContext.events` owns dispatch, typed event definitions, recursion protection,
correlation IDs, and bounded diagnostics. Core code emits events directly;
PluginManager owns plugin loading and registers listeners with the bus.
WebSockets observe public events when the web transport is available.

Before hooks run before the mutation and can cancel it. A failed or timed-out
before listener cancels the operation. After hooks describe a completed operation:
listener failures are recorded and do not turn a successful mutation into an API
failure. Plugin lifecycle hook failures still fail loading or unloading.

Listeners receive separate copies of payload data. The cancellation object is
shared during before dispatch and sealed before the mutation, so late callbacks
cannot cancel an operation that has already started. Async listeners run in the
calling task, preserving reentrant server locks; synchronous listeners run in a
worker thread. A deadline stops waiting for a synchronous callback, but cannot
terminate its thread. Plugins should avoid blocking work in hooks.

## Declaring and emitting a typed event

Declare plugin events under the plugin's module name followed by a colon. Payloads
use Pydantic models and must serialize to JSON. The bus validates and normalizes
them before any listener or transport receives them.

```python
from pydantic import BaseModel, ConfigDict
from bedrock_server_manager import PluginBase

class RefreshPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_name: str
    reason: str

class DashboardPlugin(PluginBase):
    version = "4.0.0"

    # This example is installed as dashboard.py.
    def on_load(self):
        self.api.events.define("dashboard:refresh", RefreshPayload)
        self.refresh_listener = self.api.events.listen(
            "dashboard:refresh", self.refreshed
        )

    async def refreshed(self, server_name: str, reason: str, **kwargs):
        self.logger.info("Refresh %s: %s", server_name, reason)

    async def refresh(self):
        receipt = await self.api.events.emit(
            "dashboard:refresh", server_name="example", reason="settings_changed"
        )
        if receipt.status == "partial":
            self.logger.warning("Some refresh listeners failed")
```

`events.listen()` returns a subscription token; `events.unsubscribe(token)` removes
that subscription. Listeners and definitions are removed automatically on unload.
A saved API from an unloaded plugin cannot register or emit after reload.
Plugins and external callers may emit custom events; core before, after, and
lifecycle events are reserved for the application. Legacy `send_event()` and
`listen_for_event()` remain supported through the same bus. Undeclared custom
events remain JSON-only for compatibility.

For a private custom event, pass `public=False` to `events.define()`. Public
events keep the WebSocket topic `event:<name>` and the existing `type`, `topic`,
`epoch`, `revision`, and `data` fields, with `event_id` and `correlation_id` added.
The before/after pair shares a correlation ID; nested dispatches also identify
their parent event internally.

For transport-only topic data and live dashboards, use
`self.api.websocket.websocket_broadcast` and
`self.api.runtime.register_data_provider`; see the
[plugin introduction](introduction.md) and [Native JSON UI](native_json_ui.md).

## Diagnostics and limits

`events.diagnostics()` returns copied metadata for current and recent dispatches,
including duration, listener failures, delivery counts, and correlation IDs.
Payloads and exception messages are not retained. History is bounded and held in
memory; it is not a replay log and does not survive a restart.

Administrators can read `GET /api/events` for the event catalog and JSON payload
schemas, and `GET /api/events/activity` for diagnostics. These routes require
administrator authentication. The external trigger endpoint accepts only custom
events and returns a typed dispatch summary.

The `events` settings section controls `history_limit` (200), `max_active` (256),
`max_depth` (32), `listener_timeout_seconds` (30), and `hook_timeout_seconds` (120).
Duplicate recursive dispatches with the same identity are suppressed. Capacity
and depth exhaustion produce a partial receipt and cancel before hooks. During
shutdown, plugin listeners drain before unload and the bus drains before the
WebSocket transport closes.
