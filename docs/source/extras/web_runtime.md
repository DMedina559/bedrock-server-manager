# Web runtime and graceful shutdown

The web host owns a single Uvicorn server and a `WebRuntime` controller. Core
application cleanup remains in AppContext's FastAPI lifespan: drain requests,
quiesce producers, drain managed operations, stop Bedrock servers, unload plugins,
drain events, close WebSockets, flush state and close the database.

Web start, stop and process-status proxies have been removed from AppAPI and its
Pydantic API models. CLI hosting calls the web subsystem directly; service
configuration APIs remain available. Hosting configuration and runtime responses
use their own Pydantic models.

## HTTP control

Administrators can inspect `GET /api/runtime` (`get_web_runtime`) and submit an
empty JSON object to `POST /api/runtime/shutdown` (`shutdown_web_runtime`). The
shutdown response is HTTP **202**, with the instance ID, PID, stopping phase and
reason. It confirms acceptance, not completed cleanup. The response is sent
before signalling Uvicorn to exit; Uvicorn then drains requests and runs lifespan
cleanup. Duplicate shutdown requests preserve the original reason. New API
mutations receive HTTP 503 once shutdown is accepted.

An ASGI app hosted without BSM's runtime controller returns HTTP 503 for runtime
control. Embedders can use `create_server(context, options, runtime)` or attach an
exit callback to an injected `WebRuntime`. Run one application worker per
configuration directory.

## Local CLI control

```sh
bedrock-server-manager web start --mode direct --host 127.0.0.1 --port 11325
bedrock-server-manager web start --mode detached
bedrock-server-manager web stop --timeout 180
```

Detached startup waits for HTTP readiness and reports failure if its child exits.
The hosting process owns `web_server.pid`, `web_server.control.json` and an OS-held
lock. Runtime records are written atomically and removed after cleanup, including
startup failures. A second host using the same configuration is rejected.

The control record contains a random per-instance shutdown credential. POSIX
records have owner-only permissions; Windows records inherit the configuration
directory's ACL. Protect that directory as you would other application credentials.
The credential authorizes only the shutdown route and is never returned by the
HTTP status endpoint. It is rotated at every runtime start.

`web stop` uses this credential, waits for the owner's control record to disappear,
and retains records if graceful stop fails. `--force` permits verified process
termination as a fallback, including legacy PID-only installations. Normal stops
work on Windows without calling TerminateProcess. Force can interrupt cleanup.

`--debug` enables Uvicorn debug logging. It does not start an automatic reload
supervisor. Trusted forwarding sources are configured by `web.forwarded_allow_ips`
(default `127.0.0.1`); configure your reverse proxy's address if needed.

## Service supervision

Recreate existing BSM service definitions to install the updated command and stop
policy. They preserve the selected configuration/data directories; database
configuration belongs in that configuration directory.

Generated systemd units use `Restart=on-failure`, normal SIGTERM handling, and a
180-second stop allowance. They no longer invoke a PID-based `ExecStop`. A clean
HTTP shutdown exits successfully and stays stopped without disabling autostart.
Increase the service deadline if you configure longer application stage deadlines.

Windows SCM stops signal the same runtime and wait for cleanup. Intentional HTTP
shutdown also returns through the service host normally. Runtime failures are
reported as service failures; a stop requested during startup is retained.

BSM does not change external supervisor policies. Docker `restart: always` or
`unless-stopped` can restart a process after an HTTP shutdown: stop the container
through Docker when you want it to remain stopped. Other external process managers
must likewise distinguish intentional clean exits from failure restarts.
