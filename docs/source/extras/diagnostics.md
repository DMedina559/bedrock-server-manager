# Diagnostics and support reports

Administrators can inspect BSM's current runtime without collecting raw settings, user records, task arguments, or event payloads. Diagnostics are observations, not a replacement for logs or the lightweight health endpoint.

## Inspect diagnostics in the web interface

Open **Metrics → Diagnostics** to inspect the overview, subsystem observations and available history. Check both overall health and readiness, then inspect individual subsystem status and freshness. Use **Download support report** when collecting information for a support request.

```{figure} ../../images/web_ui_green_theme.png
:alt: Diagnostics overview showing health, readiness, collection time and support report download
:width: 600px
:align: center

The diagnostic overview summarizes observations and provides a support-report download.
```

```{figure} ../../images/web_subsystem_diagnostic.png
:alt: Diagnostic subsystem cards for Runtime, State, Storage and Events
:width: 600px
:align: center

Subsystem cards expose health and observations for individual parts of the application.
```

## Read the diagnostic API

Use your normal administrator authentication:

| Route | Operation ID | Purpose |
|---|---|---|
| `GET /api/diagnostics` | `get_application_diagnostics` | Current subsystem observations |
| `GET /api/diagnostics/{subsystem}` | `get_subsystem_diagnostics` | One subsystem, such as `events` or `storage` |
| `GET /api/diagnostics/activity` | `get_diagnostic_activity` | Global active/recent events and operations, plus listener configuration |
| `GET /api/diagnostics/history` | `get_diagnostic_history` | Retained sanitized failure and lifecycle records |
| `GET /api/diagnostics/runs` | `get_diagnostic_runs` | Retained records grouped by application instance |
| `GET /api/diagnostics/trace/{correlation_id}` | `get_diagnostic_trace` | Correlated live events, tasks, and retained records |
| `GET /api/diagnostics/report` | `get_diagnostic_report` | Current observations and bounded history for a support report |

History accepts `limit` (1–200), `subsystem`, `instance_id`, `correlation_id`, `owner`, `code`, `outcome`, and `operation_id`. Results are newest first. Pass `next_cursor` as `cursor` to continue without duplicating records with equal timestamps; `truncated` indicates more matching records. Runs summarize retained records, not complete process lifetimes. A missing closing record does not prove that an instance crashed. The event catalog and filtered event details remain available through `/api/events` and `/api/events/activity`.

The summary separates readiness from overall diagnostic health and provides findings with suggested actions. Reports include an ID, generation time, backend/frontend/Python versions, operating system, database dialect, and schema revision. The report endpoint supplies a download filename.

Every section identifies its owner, collection time, source observation time, last successful reading, age, freshness, status, and typed data. Failed providers can retain their last successful data, explicitly marked stale. `unknown` means there is insufficient evidence; `unavailable` means the section could not be collected. A failed or slow provider does not hide other sections. Snapshots are collected independently and are not an atomic view of every subsystem. State's `observation_revision` orders the observation; it is not a count of committed mutations.

Runtime observations include lifecycle phase and stage. Event observations include capacity, pending workers/waits, owner timeout counts, and recent listener outcomes. Storage observations summarize domain transactions, including the last observed success or failure. Task observations omit arguments, result payloads, usernames, and exception text. WebSocket sends are serialized per client with a bounded waiting queue. `web.outbound_queue_limit` defaults to 64 outstanding sends per client; overflow rejects the newest send. Delivery receipts still report actual sends. Diagnostics expose pending/active sends, high-water marks, drops, timeouts, and fixed disconnect reasons without client identities.

Metrics include collection timing, failures, missed intervals, warm-up, and unavailable measurements. Storage includes lock contention and reload outcomes. Plugins include versions, owned listeners/workers/providers/tasks, transitions, and drain failures. Tasks include safe operation names, cancellation state, and correlation IDs. Progress remains unavailable until the running task calls `self.api.runtime.report_task_progress(percent)`. Traces connect these observations without exposing task arguments or event payloads.

## What survives restarts

Live counters, active operations, and event activity reset for each application instance. The database retains bounded lifecycle-stage records, event listener failures, failed domain transactions, and background task outcomes, provider failures, plugin transitions/failures, process-monitor failures, and transport failures. Each record includes an instance ID, time, outcome, stable code, duration, and correlation ID when available. Exception types are retained; exception messages and tracebacks stay in logs.

Diagnostic recording uses an independent best-effort queue. It never participates in the transaction it observes. Database failures and overflow increment the report's write-failure/drop counts. A crash can lose records still queued in memory; diagnostic history is not a guaranteed audit log.

Defaults retain at most 1,000 records for seven days, with a 256-record write queue. Settings under `diagnostics` configure `history_limit`, `retention_days`, `queue_limit`, `provider_timeout_seconds`, `max_providers`, and `max_providers_per_owner`. Restart the application after changing these settings. Expired records are excluded from reads and pruned during writes. Existing records remain subject to current retention limits.

The report contains metadata only, but plugin names and event names can still identify your installation. Review downloaded reports before sharing them.

## Plugin-owned observations

Plugins can register an asynchronous provider during load:

```python
from bedrock_server_manager.diagnostics import PluginValues

async def diagnostic_values():
    return PluginValues(
        health="ok",
        values={"queued": 3, "connected": True},
        units={"queued": "count"},
    )

await self.api.runtime.register_diagnostic_provider("connection", diagnostic_values)
```

The runtime assigns the section name `plugin:<plugin_name>:connection` and its owner. Providers return bounded numeric/boolean observations; arbitrary state dumps and string values are excluded. Providers must yield normally and cooperate with cancellation. A timeout cannot forcibly terminate Python code that blocks the event loop.

Providers are removed during plugin unload. An old unfinished provider prevents replacement of the same name until it drains. Registration limits bound provider counts globally and per plugin owner. Registry diagnostics show configured limits, ownership, pending providers, failures, timeouts, and rejected registrations. Built-in application providers are outside the per-plugin limit. Plugin authors can read typed diagnostics with `self.api.diagnostics.get_application_diagnostics({})`, `get_diagnostic_history({})`, and `get_diagnostic_report({})`.

Provider health defaults to `unknown`; explicitly return `ok` or `degraded` when the provider has evidence. Provider collection failures are reported separately as `unavailable`. Optional units are `count`, `seconds`, `milliseconds`, `bytes`, or `percent` and must refer to a returned value. Labels are bounded to 80 characters. Providers should report measurements rather than perform expensive probes.

## Diagnose the diagnostic subsystem

`collection` reports actual collection requests, completed collections, failures, cache hits/age, current activity, and last collection timing. Its health also reflects observed history read/write failures and an unexpectedly stopped writer. `persistence` identifies writer state and the most recent successful read/write. These observations require no additional database health probes.

Subsystem-only responses summarize the selected observations. Their `summary.ready` is `null` when runtime readiness was not observed, so a healthy plugin section can report `ok` independently. Runtime readiness requires a fresh successful runtime observation. Repeated requests for one timed-out callback that is still draining do not create additional timeout records or restart that callback.

The `recent` window aggregates recorded failures, cancellations, and timeouts for the current instance over thirty ten-second buckets. It counts observed outcomes even if the journal writer later drops them. It resets on restart and is not a rate calculation for all subsystem operations.

Event observations limit both record counts and nested listener/failure/delivery details. Defaults are 20 active and 20 recent records, with 50 entries per detail list. `diagnostics.event_record_limit` and `event_detail_limit` configure these bounds. Truncation flags distinguish partial results from complete activity. Traces report event, task, and history availability independently and preserve available sources when another source fails.

## Compare snapshots

`POST /api/diagnostics/compare` (`compare_diagnostic_snapshots`) accepts `before` and `after` snapshots and returns up to 200 metadata changes. Administrator authentication is required. Save the original JSON snapshots to compare observations later.

Comparisons include subsystem health, numeric observations, and plugin status/generation changes. Numeric deltas require snapshots from the same instance in chronological order. Counter decreases and instance changes are marked as resets instead of negative activity. Gauge decreases can still have valid negative deltas. Comparisons are observations, not an atomic transaction history.

## Optional periodic history

Set `diagnostics.snapshot_interval_seconds` to a value from 10 to 86,400 seconds to persist compact health samples and transitions while the application is running. The default is `null`, which disables periodic sampling. Restart after changing the setting.

Samples retain overall health, readiness, and subsystem status labels; they do not store full snapshots or event/task payloads. They share the history queue and retention budget with lifecycle/failure records. For example, a 60-second interval can consume 1,000 records in about 17 hours, so choose the interval and history limit together. Periodic collection failures are counted, and shutdown cancels the sampler before flushing history.

For remote support reports, the API/CLI client provides `bsm-cli diagnostics report --output bsm-support-report.json` through live OpenAPI discovery. Use an administrator account and a backend exposing `get_diagnostic_report`. Existing destinations require `--force`; incomplete downloads never replace the destination.

Diagnostic collection/recording failures contribute an actionable `diagnostics` finding to the overall summary. They do not change application readiness. `/api/health` exposes `ready` using the same loaded-state and application/web-runtime rule as diagnostics; its dependency checks remain separate from optional diagnostic health.

Periodic observations expose `periodic_status` (`disabled`, `not_started`, `running`, `stopped`, or `failed`), `last_periodic_success_at`, and `last_periodic_error_type`. Successful sample time describes collection, not guaranteed journal persistence. An unexpected worker exit or a failed sample degrades diagnostic health; a successful sample clears its last error. Removed/replaced providers cannot publish or cache observations from an earlier registration.


## Global event and operation activity

`GET /api/diagnostics/activity` reads activity across every execution chain in the
current application instance. No correlation ID is required. Optional filters are
`name` (event name), `source`, `owner`, `server_name`, `phase`, `status` (event
status), `operation_name`, `operation_id`, `sequence_id`, and `correlation_id`.
`limit` accepts 1–200; the configured diagnostic record limit also applies.
Operation filters use operation identity, name, server, source, owner, sequence,
and correlation; event name, phase, and event status only narrow events. Listener
configuration is filtered by event name and owner, not by execution-chain IDs.

The `events` section contains active and recent event metadata. Event records link
back to their operation and sequence when emitted inside an operation. The
`operations` section contains active operations and recent completed, failed, or
cancelled operations. `parent_operation_id` and `root_operation_id` describe the
ancestry; a limited response can omit ancestors. `subscriptions.items` includes
listener owners, priorities, filters, ordering, unresolved references, and delivery
statistics. Callback objects and predicates are never serialized.

The existing Events diagnostic section and support reports include operation
activity and listener details too. Correlation traces include matching operations.
A source that cannot be read does not hide other sources: unavailable global
activity sources are `null`, with errors reported in `issues` without exception
text. Traces expose operation availability separately.

Activity is bounded metadata, not an unlimited or durable event log. Event history
uses the event bus history limit; global operation history retains the latest 200
operation outcomes by default and resets on restart. It works even when event
history is disabled. Global operation results are newest first; event recent
records retain their existing oldest-to-newest order. Counts describe the whole
service, while returned records follow the filters. Truncation flags identify
partial views. The retained diagnostic journal continues to store sanitized
failure/lifecycle records under its existing retention policy. Payloads, task
arguments, credentials, and cancellation messages are excluded from these
administrator activity responses.


## Troubleshooting long operations

Use INFO logs for backup selection and completion, scheduled-run outcomes, and
operational warnings. Enable DEBUG temporarily to include API durations,
backup/restore stages, reused capture hash counts, inventory file counts and sizes, and event-listener
start/finish records. Event records include the listener owner, event ID,
deadline, outcome, and elapsed time. A hook deadline can cancel a pre-start
backup even when the same backup succeeds manually.

Backup cancellation logs identify the last reported stage. Cancellation waits
for owned filesystem workers to stop before releasing locks; a timeout may
therefore take longer than its configured deadline to return. Inventory checks
for cancellation between files and while hashing file contents.

Unexpected exceptions retain tracebacks in application log files. Normal API
responses and background-task errors use sanitized messages, without exception
text or tracebacks. Expected validation and state conflicts are DEBUG records;
repeated diagnostic-store/provider failures are rate limited. Stage and timing
records omit request bodies; raw WebSocket protocol frame dumps are suppressed.
