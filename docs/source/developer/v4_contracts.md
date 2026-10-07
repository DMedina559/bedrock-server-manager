# Migrating to 4.0 contracts

Version 4.0 intentionally changes the HTTP and plugin contracts. Generate client
types from the running application's OpenAPI schema instead of duplicating the
Python models. Pydantic is an explicit runtime dependency.

## Plugin calls and events

Use domain namespaces and one request model or mapping:

```python
from bedrock_server_manager.api.models import StartServerRequest

result = await self.api.server.start(StartServerRequest(server_name="example"))
self.logger.info(result.message)
```

Flat operation names and plural aliases such as `api.servers` are removed.
Runtime capabilities live at `api.runtime.run_task`,
`api.runtime.server_lifecycle_manager`, and
`api.runtime.register_data_provider`. Data operations return their declared
Pydantic response. Read attributes directly; use `model_dump(mode="json")` at
transport boundaries.

The generated protocols in `plugins/api_types.py` provide static typing and
autocomplete. After changing a registered API, run
`python scripts/generate_plugin_api.py`; use `--check` to detect drift.
Run `python scripts/check_api_callers.py` to check direct API calls and
deferred targets passed to `run_task` or `functools.partial` for legacy arguments.

Before-event callbacks receive a typed `request`; after-event callbacks also
receive a typed `result`. These are independent snapshots. Cancellation uses
the separate event control object. WebSocket event messages serialize models
to JSON and exclude runtime context. Custom event payloads must contain JSON
values; arbitrary objects are rejected.

Use `get_plugin_setting` and `set_plugin_setting` on `PluginBase` for settings
scoped to the calling plugin. Plugin identity is injected by the bridge and
cannot be supplied in the request. `SettingsState.plugin_settings` is the sole
persistent settings source; plugin metadata no longer duplicates it.

## HTTP and background tasks

Server start, stop, and restart endpoints await completion and return HTTP 200
with `StartServerResponse`, `StopServerResponse`, or `RestartServerResponse`.
These responses contain `server_name`, `status`, `outcome`, and `message`; they
have no `task_id`. Clients should await the response and display its outcome.
Failures return the standard HTTP error envelope. Start completion means the
process was launched, rather than a guarantee that game clients can connect.

Long-running task submission returns `TaskAcceptedResponse` with `status: "accepted"` and
`task_id`. Polling and WebSocket updates share `TaskSnapshot`:

| Field | Meaning |
| --- | --- |
| `status` | `queued`, `running`, `completed`, `failed`, or `cancelled` |
| `result` | JSON serialization of the operation response, or null |
| `error` | Structured API error, or null |

An operation that returns `status: "skipped"` still completes successfully;
inspect its result to determine the operation outcome. Task polling is scoped
to the authenticated owner. Active tasks are never evicted to make room for
new submissions.

HTTP failures use `{"error": {"code": "...", "message":
"...", "details": {}}}`. Read the HTTP status and error code. Invalid request
input returns 422; invalid operation output returns 500. Internal exception
details are logged and omitted from public errors. Registration and backup
listing have dedicated response schemas. Backup listings use `backups` rather
than `details.all_backups`.

## State, runtime, and persistence

Persistent records remain validated Pydantic models with JSON-only extension
data. State containers, changesets, plugin instances, locks, and runtime handles
are ordinary Python dataclasses. Do not serialize runtime containers.

State reads return independent snapshots. Setters revalidate incoming records;
settings changes validate a complete candidate snapshot before changing live
state. Partial server and user updates preserve unspecified fields.

Storage acknowledges dirty records only after a successful commit and only if
the live value still matches the saved snapshot. SQLite lock retries replay
the whole write. Listeners run after commit, outside the write lock, and receive
independent changesets. Reloading state replaces stale clean records and preserves pending dirty updates.
The legacy `monitoring.max_retiries` key is normalized to `max_retries` on load.
