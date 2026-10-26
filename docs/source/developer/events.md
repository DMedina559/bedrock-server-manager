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

## Operation sequences

Event delivery and operation outcomes are separate. A completed dispatch means
listeners finished; it does not establish that a backup or update succeeded.
The application owns a bounded `OperationService`, shared explicitly with server
components. Start, stop, restart, update, and backup requests establish operation
scopes. The full-backup service records `backup.create` for internal and API callers.
Update backups use the public backup hooks, including cancellation.

Awaited nested calls share a sequence, retain their own operation IDs, and record
parent-operation ancestry independently of event nesting. Each sequence retains
up to 200 finished results; at most 256 root sequences and 64 nested operations
are permitted. Root exit releases its sequence-local results on success, failure, and cancellation.
A separate bounded global metadata history retains recent outcomes for diagnostics;
it does not make results from other sequences visible through `operations.results()`.
These limits do not depend on event diagnostic history. Results contain metadata,
component coverage, and outcomes, without payloads, configuration contents, or
credentials. They are coordination data, not a durable backup inventory.

Plugins read immutable snapshots through `self.api.operations`. These capabilities
are bound to the original event-bus lifetime and plugin generation. Detached
managed tasks and separately created asyncio tasks cannot inherit an active
sequence. Await nested work directly when its result must affect the current
operation. Synchronous event callbacks may inspect their caller's active context.

Server start takes its reentrant operation lock and checks running state before
pre-start hooks. Already-running requests return without running these hooks.
Decorated listeners accept `priority`, with higher values first and stable
registration order for ties. Auto-update uses 100; backup-on-start uses 0.

See [plugin operation context](plugins/contracts.md#operation-context) for queries
and [bundled backup policy](../features/default_plugins.md#backup-reuse-within-an-operation).
