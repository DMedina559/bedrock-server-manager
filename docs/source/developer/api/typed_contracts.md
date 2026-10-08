# Typed API contracts

All 80 data API operations across 17 domains use contract version 2. Each accepts
one operation-specific request and returns a concrete response model. All 61
registered operations expose model names and JSON Schemas; 57 retain ordinary
plugin visibility. The complete inventory includes unregistered application APIs.

## Calling data operations

Every data operation takes one request model and returns a response model:

```python
from bedrock_server_manager.api.models import StartServerRequest

result = await self.api.server.start_server(
    StartServerRequest(server_name="example")
)
if result.outcome == "started":
    self.logger.info(result.message)
```

The bridge also accepts a single mapping and validates it against the same model:

```python
result = await self.api.start_server({"server_name": "example"})
```

Do not pass `app_context` or `plugin_name`. The bridge injects trusted runtime
dependencies and rejects overrides, including positional overrides. Context and
Core objects are never request or response fields. Core consumers can use the
mapping interface without importing the API models.

Application callers supply context separately:

```python
from bedrock_server_manager.api.models import RestartServerRequest
from bedrock_server_manager.api.server import restart_server

result = await restart_server(
    RestartServerRequest(server_name="example", send_message=False),
    app_context=app_context,
)
```

## Lifecycle migration notes

| Before | After |
| --- | --- |
| `await self.api.start_server(server_name="example")` | `await self.api.start_server(StartServerRequest(server_name="example"))` |
| `await self.api.stop_server("example")` | `await self.api.stop_server(StopServerRequest(server_name="example"))` |
| `await self.api.restart_server("example", send_message=False)` | `await self.api.restart_server(RestartServerRequest(server_name="example", send_message=False))` |
| `result["message"]` or `result.get("status")` | `result.message` or `result.status` |
| A returned dictionary for an operational failure | A raised application exception |

Import `StopServerRequest` and `RestartServerRequest` from the public
`bedrock_server_manager.api.models` module alongside `StartServerRequest`.
Use `result.model_dump(mode="json")` at serialization boundaries.

An already-running start produces `outcome="already_running"`; an already-stopped
stop produces `outcome="already_stopped"`. Both are successful idempotent results.
Restarting a stopped server produces `outcome="started"`, while a stop/start cycle
produces `outcome="restarted"`. All successful lifecycle responses have
`status="success"`, `server_name`, `outcome`, and `message`.

These are breaking call and failure-contract changes on the development branch.
No automatic legacy scalar-call adapter is installed for migrated operations.
Update third-party callers before adopting this revision. The separately released
`bsm-cli` package must also adopt these contracts if it calls these functions
directly; its source is outside this repository.

## Validation and failures

Unknown request fields and invalid server names fail before plugin events or
server operations. Request model instances are revalidated to prevent constructed
or subsequently mutated instances from bypassing validation. Response instances
are also revalidated. Responses prevent attribute reassignment, but nested data
is not deeply immutable.

Defaults are validated using the same strict rules as supplied values. JSON
payloads reject NaN and positive/negative infinity, including inside nested lists
and dictionaries, so serialization cannot silently replace them with null.

The Pydantic mypy plugin checks model constructors and frozen fields. API model
modules additionally reject untyped definitions and unparameterized containers.
Use typed constructors when building responses from known fields; reserve
`model_validate` for data loaded from mappings or other runtime boundaries.

Catch existing application exceptions such as `ServerStartError` and
`ServerStopError` for operation failures. Plugin cancellation raises
`APICancelledError`, and suppresses execution and the after-event. Invalid request
data raises Pydantic `ValidationError`. Unexpected exceptions propagate to Python
callers. Invalid output is an `APIResponseValidationError`, an implementation
failure rather than a client-input failure.

Serialized boundaries can use `bedrock_server_manager.api.errors.error_response`
to obtain an `APIErrorResponse`. Its stable code and safe message omit raw
exception text and input values. Background tasks serialize typed success results
and store structured failure results; exceptions remain in diagnostic logs.

Lifecycle event payloads retain top-level `server_name` and their existing event
names and identities. After-event results are JSON dictionaries, preserving event
consumers' serialization interface. A canceled or failed stop prevents restart's
start phase. PID cleanup occurs only after a stop succeeds or the server is
confirmed stopped.

## Discovery and documentation

Version-2 discovery entries add `request_model`, `request_schema`,
`response_model`, `response_schema`, and `error_schema`. Request schemas use
Pydantic validation mode; output/error schemas use serialization mode. Nested
definitions and references are preserved. Existing parameter metadata remains
available for reflection.

Runtime dependencies are omitted from public parameter metadata. Internal APIs
are inaccessible and excluded from ordinary plugin discovery, even when a plugin
passes `include_internal=True`. Core-created bridges retain internal visibility.

`APIDocsGenerator` renders contracts and import/call examples. New contracts with
missing model annotations, extra scalar parameters, request defaults, or runtime
fields fail registration instead of silently exposing incomplete metadata.

## Domain behavior and runtime integrations

- All-settings responses place configuration under `result.settings`, rather than
  adding arbitrary keys to the response envelope. Values use validated JSON types.
- `validate_property_value` returns `valid=False` for a checked invalid value.
  This is a successful validation query. `set_properties` raises `UserInputError`
  when an update contains an invalid value, before writing properties.
- Status reconciliation returns successful completion with an `errors` list for
  partial discovery failures and an explicit updated server count.
- Lock contention returns a typed `status="skipped"` acknowledgement where the
  original operation could skip concurrent work. Operational failures raise.
- Plugin-target requests use `target_plugin_name`; trusted caller identity is
  never supplied as request data. Plugin status events retain `plugin_name` and
  `enabled` fields for listeners and recursion identity.
- Requests and responses use `strict=True` and reject extra fields. Permission,
  pack, and backup type fields explicitly normalize case before literal validation.
  Nested allowlist records support name-only entries with optional XUIDs.
- Web-service passwords use `SecretStr`, are omitted from serialization and
  representation, and are unwrapped only when calling native service management.

Task submission, lifecycle context managers, and provider registration are native
runtime capabilities in `plugins/runtime_capabilities.py`. They are excluded from
the serializable data API inventory and schema discovery because they carry live
functions or yield context managers. Existing plugin access through `self.api`
is preserved with trusted dependency injection. Registration failures propagate.

```python
async def collect(value):
    return value

task_id = await self.api.run_task(collect, 42, username="admin")
await self.api.websocket.register_data_provider("custom-topic", collect)
async with self.api.server_lifecycle_manager(
    server_name="example", stop_before=True, start_after=True
):
    await perform_native_operation()
```

HTTP routes construct operation requests and serialize typed results. Invalid API
requests reaching the transport handler return HTTP 422 with safe field locations
and error codes. Raised not-found, input, cancellation, and internal failures map
to HTTP 404, 400, 409, and 500 respectively. Existing routes with explicit error
handling retain their endpoint-specific messages and status decisions. Background
tasks store JSON success models and safe structured failure envelopes.

The repository's CLI, Core bridge consumers, bundled plugins, sample plugins,
routers, task execution, event extraction, and documentation generator are
updated. Third-party plugins and the separately released `bsm-cli` package must
adopt version-2 contracts; they are outside this repository.

See [the complete inventory](contract_inventory.md) for every request/response pair.
