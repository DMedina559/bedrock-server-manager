# Diagnostics and health architecture

`Diagnostics` coordinates bounded provider observations; composition attaches narrow callbacks from application services. Health evaluation converts evidence into findings. History stores sanitized records independently, activity summarizes recent failures, sampling optionally persists compact health observations, and comparison evaluates saved snapshots.

## Collection contracts

Provider failures must preserve other sections. Cached last-success data is explicitly stale; `unknown` and `unavailable` are distinct from a measured zero. Readiness uses application/web lifecycle evidence and remains separate from optional diagnostic health. Snapshots are observations, not atomic transactions.

Plugin providers return bounded `PluginValues` through owned runtime capabilities. Registration and unload enforce ownership and generation checks. A timed-out provider that is still draining cannot be replaced or repeatedly restarted. See [administration and provider examples](../extras/diagnostics.md) for settings, endpoints and retention semantics.

## Persistence and privacy

The bounded journal is best effort and separate from domain commits. Queue overflow, writer/read failures and stopped workers are themselves observable. A crash can lose queued records. Do not treat retained support history as a guaranteed audit trail.

Record stable codes, durations, correlation and instance IDs; keep payloads, credentials, exception messages and tracebacks out of reports. New observations need an explicit freshness policy, bounded schema and failure behavior.

Test provider isolation, timeout/drain behavior, replacement generations, stale readings, health evidence, redaction, pagination, retention and restart persistence. Comparison tests should cover instance changes and counter resets. Use `tests/diagnostics` and `tests/services/test_health.py`.

See [diagnostics reference](reference/diagnostics/index.rst). Existing HTTP snapshots remain the diagnostics transport; no diagnostic WebSocket update protocol is implemented.
