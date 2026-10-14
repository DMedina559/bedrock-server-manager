# Adding an API contract

Choose the domain owner before exposing an operation. Core receives narrow dependencies; Python API modules adapt application context into those dependencies. HTTP routers handle authentication and transport conversion, while the plugin bridge injects caller identity.

## Requests, results and errors

Declare strict Pydantic request/response models in `api.models`, using shared contracts where appropriate. Document meaningful units, side effects and failure semantics instead of repeating every model field in docstrings. Apply the established `api_method` registration and `validate_contract` validation patterns, and export plugin request models from `api.models` when needed.

Requests must fail before events or side effects. Response validation failures are internal errors, not invalid client input. Return declared models; preserve partial/skipped outcomes. When a committed mutation has a failed follow-up, retain its validated partial result and committed identity rather than claiming rollback.

Domain exceptions propagate to the boundary. The shared classifier chooses safe error codes, messages and HTTP status; logs retain traceback ownership. Do not catch every exception and return success-shaped data. Cancellation remains cancellation.

## HTTP and consumer changes

Give each route a unique, stable `operation_id`, typed inputs and response models, and explicit access dependencies. Check the running OpenAPI schema against request names, nullable fields and transport responses. Acceptance of a task does not prove its final operation succeeded.

Run `python scripts/generate_plugin_api.py` after changing the plugin registry and `python scripts/generate_plugin_docs.py` after changing contracts or descriptions. Check both generated outputs with `--check`. Use `python scripts/export_openapi.py --help` for schema export options and `python scripts/check_api_callers.py` to catch invalid internal callers.

Regenerate affected frontend, Python API/CLI, Minecraft and Home Assistant consumer contracts against the selected backend revision. Coordinate package releases so dependency requirements point to published compatible versions. Keep client repository scripts and generated files in their own repositories.

Test request rejection before side effects, declared outputs, partial failures and route permissions. See [model reference](reference/contracts/index.rst), [API reference](api/api.rst) and [plugin contract guide](plugins/contracts.md).
