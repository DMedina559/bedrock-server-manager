# Runtime ownership and cleanup

Application composition owns storage, state, services, events and plugin resources. `create_web_app` assembles FastAPI; the host creates Uvicorn and `WebRuntime`. CLI direct/detached hosting and Windows SCM compose these components without public API start/stop proxies.

## Lifespan and shutdown

Shutdown admission rejects new mutations before draining managed work. Cleanup quiesces producers, drains operations, stops Bedrock servers, unloads plugins, drains events, closes transports and disposes storage. Consult the implementation for stage ordering and configured deadlines when adding a resource.

Each resource needs one cleanup owner and a startup-failure path. A timeout cannot forcibly terminate synchronous work. Cancellation should be propagated after cleanup rather than converted into ordinary success. Register resources through owned plugin tasks, loops, providers and router lifespans.

The host owns the process lock, PID/control records and per-instance shutdown credential. API acceptance means stopping was requested, not that cleanup finished. Systemd, Windows SCM and container supervisors have different restart semantics; see [runtime administration](../extras/web_runtime.md).

## Embedding and tests

An embedded ASGI application needs an injected runtime exit callback for shutdown control. Run one worker per configuration directory. Preserve authentication and mutation admission when adding routes or middleware; see [web composition](web_architecture.md).

Test startup failure, duplicate shutdown, drain deadlines, cancellation and cleanup ownership. Platform-specific process/service tests should exercise their distinct behavior without broadening the Python CI matrix beyond supported minimum and maximum versions.

See [runtime references](reference/runtime/index.rst) and [service lifecycle](reference/services/lifecycle.rst).

## Server preparation and conflicting actions

Start, stop, restart, update and restore reserve the server in operation activity
before running their hooks. A conflicting request from another operation sequence
fails immediately with an operation conflict instead of waiting and unexpectedly
running later. Nested preparation, backups and restart steps in the same sequence
remain supported. Different servers can operate concurrently.

Automatic update on start must succeed before launch. Its callback has a one-hour
outer safety deadline; backup, download and installation each have their own
configurable deadline, so a slow backup does not consume the download budget.
Other event callbacks retain their existing deadlines. The optional backup-on-start
plugin retains its own timeout and required-backup setting.

Operation activity includes `stage`: `backing_up`, `downloading`, `installing`,
`starting`, then `ready`. Stages update the current operation and its same-server
parents. A successful start response still means the process was spawned;
`ready` is recorded only after that process generation reports readiness.
A failed operation retains the stage where it stopped. These records use the
existing bounded activity history and do not introduce background HTTP tasks.

Installation cancellation keeps the server reserved while its worker drains and
file replacement rolls back. Cancellation checks between replacements allow the
worker to stop cooperatively. Deadlines therefore request cancellation; cleanup
can extend the elapsed time beyond the deadline. Cancelled installations are
marked `ERROR` and never proceed to launch automatically.
