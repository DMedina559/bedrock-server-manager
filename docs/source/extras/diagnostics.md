# Diagnostics and support reports

Administrators can inspect BSM's current runtime without collecting raw settings, user records, task arguments, or event payloads. Diagnostics are observations, not a replacement for logs or the lightweight health endpoint.

## Read the diagnostic API

Use your normal administrator authentication:

| Route | Operation ID | Purpose |
|---|---|---|
| `GET /api/diagnostics` | `get_application_diagnostics` | Current subsystem observations |
| `GET /api/diagnostics/{subsystem}` | `get_subsystem_diagnostics` | One subsystem, such as `events` or `storage` |
| `GET /api/diagnostics/history` | `get_diagnostic_history` | Retained sanitized failure and lifecycle records |
| `GET /api/diagnostics/report` | `get_diagnostic_report` | Current observations and bounded history for a support report |

History accepts `limit` (1–200), `subsystem`, `instance_id`, and `correlation_id`. Results are newest first; `truncated` indicates that more matching records exist. The event catalog and filtered event details remain available through `/api/events` and `/api/events/activity`.

Every section identifies its owner, collection time, status, and typed data. `unknown` means there is insufficient evidence; `unavailable` means the section could not be collected. A failed or slow provider does not hide other sections. Snapshots are collected independently and are not an atomic view of every subsystem. State's `observation_revision` orders the observation; it is not a count of committed mutations.

Runtime observations include lifecycle phase and stage. Event observations include capacity, pending workers/waits, owner timeout counts, and recent listener outcomes. Storage observations summarize domain transactions, including the last observed success or failure. Task observations omit arguments, result payloads, usernames, and exception text. Direct WebSocket delivery reports counts; it does not invent queue measurements for a transport that has no outbound queue.

## What survives restarts

Live counters, active operations, and event activity reset for each application instance. The database retains bounded lifecycle-stage records, event listener failures, failed domain transactions, and background task outcomes. Each record includes an instance ID, time, outcome, stable code, duration, and correlation ID when available. Exception types are retained; exception messages and tracebacks stay in logs.

Diagnostic recording uses an independent best-effort queue. It never participates in the transaction it observes. Database failures and overflow increment the report's write-failure/drop counts. A crash can lose records still queued in memory; diagnostic history is not a guaranteed audit log.

Defaults retain at most 1,000 records for seven days, with a 256-record write queue. Settings under `diagnostics` configure `history_limit`, `retention_days`, `queue_limit`, `provider_timeout_seconds`, `max_providers`, and `max_providers_per_owner`. Restart the application after changing these settings. Expired records are excluded from reads and pruned during writes. Existing records remain subject to current retention limits.

The report contains metadata only, but plugin names and event names can still identify your installation. Review downloaded reports before sharing them.

## Plugin-owned observations

Plugins can register an asynchronous provider during load:

```python
from bedrock_server_manager.diagnostics import PluginValues

async def diagnostic_values():
    return PluginValues(values={"queued": 3, "connected": True})

await self.api.runtime.register_diagnostic_provider("connection", diagnostic_values)
```

The runtime assigns the section name `plugin:<plugin_name>:connection` and its owner. Providers return bounded numeric/boolean observations; arbitrary state dumps and string values are excluded. Providers must yield normally and cooperate with cancellation. A timeout cannot forcibly terminate Python code that blocks the event loop.

Providers are removed during plugin unload. An old unfinished provider prevents replacement of the same name until it drains. Registration limits bound provider counts globally and per owner. Plugin authors can read typed diagnostics with `self.api.diagnostics.get_application_diagnostics({})`, `get_diagnostic_history({})`, and `get_diagnostic_report({})`.
