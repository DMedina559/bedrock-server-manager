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
