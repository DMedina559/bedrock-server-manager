# Event architecture

The application owns `EventBus`; plugins own scoped capabilities, and core accepts the `EventPublisher` protocol. Pass a publisher or the specific callback a function needs instead of the entire application context. WebSockets attach as observers, so core can run without HTTP hosting.

## Dispatch and failure ownership

Before-operation hooks validate and can veto work. Listener failure, timeout, or recursive before dispatch prevents the nested mutation. Notification and transport observer failures are recorded without undoing committed work. Lifecycle hook failures can prevent plugin activation or unload.

Payload models normalize data at dispatch. Listeners receive separate payload copies; the cancellation control is shared and sealed before mutation. Event and correlation IDs link related activity; they are not database transaction IDs.

Synchronous callbacks run in bounded workers. A timeout stops waiting, not the thread; outstanding work continues to consume capacity. Unload signals cooperative cancellation and drains owned work before a replacement generation can activate. Prefer asynchronous hooks and bounded external I/O.

## Extending and testing

Declare built-in payloads in the registry and use the event decorator at operation boundaries. Core status/player notifications have standalone contracts. Custom plugin declarations, priorities, queued delivery, ownership and waits are documented in [the plugin event guide](plugins/custom_events.md).

Test cancellation before side effects, observer isolation, recursion, capacity, controlled elapsed time and unload/reload behavior. Use `tests/events` and plugin ownership tests as examples. Regenerate the event catalog after changing definitions.

See [event references](reference/events/index.rst) and [diagnostics architecture](diagnostics.md). Diagnostic live counters reset on restart; retained failure records are a separate best-effort journal. There is no diagnostic change-stream protocol.
