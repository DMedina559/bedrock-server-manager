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
events remain JSON-only through legacy `send_event()` for compatibility.
Native `events.emit()` requires a declaration owned by the emitting plugin.

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
including pending worker and wait counts, workers and timeouts by owner,
rejections by reason, per-listener subscription IDs, callback names, durations, outcomes,
listener failures, delivery counts, and correlation IDs.
Payloads and exception messages are not retained. History is bounded and held in
memory; it is not a replay log and does not survive a restart.

Administrators can read `GET /api/events` for the event catalog and JSON payload
schemas, and `GET /api/events/activity` for diagnostics. These routes require
administrator authentication. The external trigger endpoint accepts only custom
events and returns a typed dispatch summary.

The `events` settings section controls `history_limit` (200), `max_active` (256),
`max_depth` (32), `listener_timeout_seconds` (30), and `hook_timeout_seconds` (120).
`max_workers` bounds outstanding synchronous callbacks globally, including queued
and timed-out work; by default it follows `max_active`. `max_workers_per_owner`
can impose a tighter owner limit and otherwise follows the global worker limit.
Worker capacity returns only when the underlying callback finishes. Rejections
produce `event_capacity` listener failures and increment `worker_capacity` diagnostics.

Duplicate recursive notifications with the same identity are suppressed.
Recursive before-operation hooks cancel the nested operation before mutation. Capacity
and depth exhaustion produce a partial receipt and cancel before hooks. During
shutdown, plugin listeners drain before unload and the bus drains before the
WebSocket transport closes. Draining signals cooperative cancellation immediately.
If a plugin's old callbacks cannot drain, its status becomes `ERROR`, reload fails,
and subsequent loads remain blocked until those callbacks finish. Transport
observer failures are recorded but cannot veto an operation, even in strict mode.
Observers use the notification timeout, including when observing a before hook.

Listeners accept `priority` (default zero); higher priorities run first, with
registration order breaking ties. Ordinary hooks always run before transport
observers. This applies to `listen()` and `once()`:

```python
self.api.events.listen("before_server_start", self.check_maintenance, priority=100)
```

## Filtered activity

The activity route accepts `name`, `owner`, `correlation_id`, `status`, and `limit`.
Owners use the bus namespace, such as `plugin:dashboard` or `transport:websocket`.
An owner matches the producer source or any listener involved in a dispatch.
The limit bounds each returned list; recent history keeps its chronological order
and includes the newest matching records. Counters remain totals for the bus.

```text
GET /api/events/activity?owner=plugin:dashboard&status=partial&limit=20
```

Plugins can apply the same validated filters:

```python
from bedrock_server_manager.events import EventActivityQuery

activity = self.api.events.diagnostics(
    EventActivityQuery(name="dashboard:refresh", limit=20)
)
```

Receipts include `rejection_reason`: `recursion`, `depth_limit`, `capacity`, or
`shutdown`. Depth/capacity receipts carry distinct failure codes and cancel
before-operation controls. Rejected dispatches do not increment the listener
failure counter. Emitting into a closed bus raises `EventDispatchRejected`, a
`RuntimeError` subclass whose `record` holds the shutdown rejection metadata.

## One-shot listeners and event waits

Use `once()` for a callback that should run for its first matching dispatch. The
subscription is consumed before the callback starts, including when that callback
fails or another emission overlaps it. A persistent and a one-shot registration
of the same callback are distinct subscriptions.

```python
self.api.events.once("dashboard:refresh", self.refreshed)

payload = await self.api.events.wait_for(
    "dashboard:refresh",
    predicate=lambda **data: data["server_name"] == "example",
    timeout=30,
)
```

`wait_for()` returns a copy of the listener keyword payload, preserving typed
request/result objects. Predicates receive the ordinary listener arguments, must
be synchronous and quick, and may reject unmatched events by returning false.
A predicate exception reaches the waiting caller without failing the emitter.
The timeout must be finite and positive. The temporary subscription is removed
on a match, timeout, exception, or caller cancellation. Plugin unload and bus
shutdown cancel pending waits. Helpers receive private events too.

A wait subscribes when its coroutine starts running, so start it before triggering
the operation whose event you expect; it does not replay prior emissions.

The registry caches Pydantic validators and synchronizes declaration, lookup, and
removal across worker threads. Owner, phase, identity, and visibility conflicts
are rejected. Multiple payload variants require explicit registration; core
shared event declarations opt into this, while plugin `define()` rejects accidental
contract replacement. Event envelopes require epoch/revision together and
positive JavaScript-safe revisions; transport counts reuse the shared delivery
invariant that every targeted recipient has an outcome.

## Core dependency boundaries

Application composition owns the bus. Core server handles receive an
`EventPublisher` rather than AppContext; status changes run through
`ServerConfiguration.set_status(status, events)`. Player observations use
`publish_player_snapshot(events, PlayerSnapshot(...))` and return an `EventRecord`.
The process monitor retains rejected snapshots for a later retry, while partial
listener delivery is recorded without replaying handlers that already succeeded.
The publisher supplies revision metadata, so core producers do not reach into a
global revision clock.

Non-API operation hooks can receive a keyword-only `events` bus explicitly.
That dependency is excluded from event payloads. API operation hooks retain their
AppContext adapter. Event-only HTTP handlers resolve a bus dependency, and plugin
native event capabilities capture their original bus and generation for the
entire runtime lifetime. A stale capability cannot follow AppContext to a new bus
after shutdown/load.

Importing `bedrock_server_manager.events` does not initialize API registration,
plugins, or HTTP. Public root exports remain available through lazy imports;
creating AppAPI explicitly registers built-in API adapters. The legacy unused
`plugins.util.broadcast_event` transport helper has been removed; public events
use the bus observer.

Payload declarations reject reserved runtime fields (`app_context`, `current_user`,
`event`, `_triggering_plugin`, and `cancellation_event`) before a publisher runs.
Delivery aggregation requires one owner and combines only recipient counts.

Synchronous listeners remain owned while their worker thread runs, including
when dispatch times out. An optional `cancellation_event` parameter receives a
threading event signaled on timeout/cancellation/shutdown; cooperative workers
should check it and return promptly. Plugin unload drains worker completion within
its lifecycle deadline. A deadline cannot forcibly terminate a worker thread.
