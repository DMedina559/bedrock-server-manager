# Scheduled tasks in plugins

Plugins can register custom server tasks in BSM's unified scheduler so administrators can schedule them per server on the **Scheduler** page or via `bsm-cli scheduler`.

## Choose the right execution model

BSM provides four distinct ways for plugins to run asynchronous or periodic work. Pick the mechanism that matches who configures the schedule and how long the work runs:

| Mechanism | Configured by | Scope | When to use |
|---|---|---|---|
| `@scheduled_task` | Administrator (Scheduler UI / CLI) | Per server, calendar time & weekdays | Custom plugin logic that administrators schedule at specific wall-clock times (e.g., custom world maintenance, announcements, external syncs) |
| `scheduled_apis` / `register_api_task` | Administrator (Scheduler UI / CLI) | Per server, calendar time & weekdays | Exposing an existing `@api_method` in the scheduler with auto-derived option schemas |
| `@task_loop(interval=...)` | Plugin author (code / plugin settings) | Plugin-wide fixed interval | Continuous background polling or housekeeping that runs automatically whenever the plugin is enabled (see [Background tasks](task_manager.md#using-task_loop-for-periodic-tasks)) |
| `self.api.runtime.run_task(...)` | Triggered on demand (HTTP route / event) | One-off managed background task | Long-running user-initiated operations that return a `task_id` for progress tracking (see [Background tasks](task_manager.md)) |

## Declare custom scheduled tasks with `@scheduled_task`

Decorate an `async` method on your `PluginBase` subclass with `@scheduled_task`:

```python
from pydantic import BaseModel, ConfigDict, Field
from bedrock_server_manager import PluginBase, scheduled_task


class AnnounceOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message: str = Field(
        default="Scheduled maintenance starting soon!",
        min_length=1,
        max_length=200,
        description="Message broadcast to players in-game.",
    )
    repeat_count: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of times to broadcast the message.",
    )


class MaintenancePlugin(PluginBase):
    version = "1.0.0"

    @scheduled_task("announce", timeout_seconds=120, requires_server_lock=False)
    async def announce_maintenance(
        self,
        *,
        server_name: str,
        options: AnnounceOptions,
        execution_context: dict,
    ):
        """Broadcast a scheduled announcement to a running server."""
        self.logger.info(
            "Running announcement for %s (slot=%s, attempt=%s)",
            server_name,
            execution_context["slot"],
            execution_context["attempt"],
        )
        for _ in range(options.repeat_count):
            await self.api.server.send_command(
                {"server_name": server_name, "command": f"say {options.message}"}
            )
```

### Automatic inference and naming

When `PluginManager` loads your plugin, `@scheduled_task` automatically resolves metadata from the method signature:

- **Task name (`<plugin_name>:<task>`):** Passing `@scheduled_task("announce")` in `maintenance_plugin` registers `maintenance_plugin:announce`. Calling `@scheduled_task` without arguments defaults to `<plugin_name>:<method_name>`. If you include an explicit prefix, it must match your plugin's namespace (`<plugin_name>:...`).
- **Options schema (`options_model`):** If `options_model` is omitted on the decorator, BSM inspects the `options` parameter annotation. When annotated with a `pydantic.BaseModel` subclass (such as `options: AnnounceOptions`), that model is used automatically.
- **Execution context (`with_context`):** Including `execution_context` in the method signature automatically enables `with_context=True` even when not passed to the decorator.
- **Description:** If `description` is omitted, the first line of the method's docstring is published in the scheduler's task catalog.

### Options validation and UI schema generation

When a task defines an `options_model`:

1. **Save-time validation:** Saving a schedule validates `options` against `options_model` before committing to the database.
2. **Run-time validation:** Options are validated again immediately before each scheduled or manual execution. If `options` is annotated with your `BaseModel` subclass, the handler receives a validated model instance (or a validated `dict` if unannotated).
3. **Dynamic UI & CLI forms:** `list_schedules` exports `options_model.model_json_schema()` under `available_tasks` (`task_schemas`), which the Web UI (**Scheduler** page) and `bsm-cli scheduler save` use to render labeled inputs, defaults, and choices.

Use `ConfigDict(extra="forbid", strict=True)` on your options models so unknown keys and invalid types are rejected cleanly.

## Expose existing APIs with `scheduled_apis`

If your plugin (or a core API domain) already exposes an `@api_method` that accepts `server_name`, you can register it as a scheduled task without writing a wrapper handler.

Declare `scheduled_apis` on your `PluginBase` subclass:

```python
from bedrock_server_manager import PluginBase


class CustomBackupPlugin(PluginBase):
    version = "1.0.0"

    scheduled_apis = [
        {
            "name": "export_world",
            "api_method": "world.export_world",
            "description": "Export the server world through CustomBackupPlugin.",
            "default_options": {},
            "timeout_seconds": 600,
            "requires_server_lock": True,
        },
        # Tuple shorthand: (task_name, api_method)
        ("scan_players", "player.scan_and_update_player_db"),
    ]
```

Each dictionary entry in `scheduled_apis` supports the following keys:

| Key | Type | Default | Description |
|---|---|---|---|
| `api_method` (or `api`) | `str` or `@api_method` callable | *(required)* | Target `@api_method` callable or dotted `<domain>.<method>` path |
| `name` | `str` | Derived from `api_method` | Task name suffix (automatically prefixed with `<plugin_name>:`) |
| `options_model` | `type[BaseModel] \| None` | Auto-derived from request model | Explicit Pydantic model for schedule options |
| `default_options` | `dict[str, Any] \| None` | `None` | Default option overrides applied to the derived `options_model` |
| `slot_field` | `str \| None` | `"schedule_slot"` if present on request | Request field that receives `execution_context["slot"]` |
| `timeout_seconds` | `float \| None` | `300` | Per-attempt execution timeout in seconds |
| `requires_server_lock` | `bool` | `True` | Whether to acquire the server's `operation_lock` before running |
| `description` | `str` | Method docstring | Human-readable description shown in the Scheduler UI |

You can also register API tasks dynamically during `on_load` via `self.api.runtime.register_api_task`:

```python
self.api.runtime.register_api_task(
    "export_world",
    "world.export_world",
    description="Export the server world through CustomBackupPlugin.",
    timeout_seconds=600,
    requires_server_lock=True,
)
```

### How `register_api_task` wraps an API method

- **Auto-derived `options_model`:** If `options_model` is not supplied, the scheduler inspects the target `@api_method`'s Pydantic request model and generates a schedule options model containing all fields except `server_name` and `schedule_slot` (which are injected automatically at execution time).
- **Default options (`default_options`):** Supply a dictionary of default request fields to pre-populate or override defaults on the derived options model.
- **Result handling & deferral:** If the wrapped API returns a response with `status="skipped"` because the server's `operation_lock` is busy or an operation is already in progress, the wrapper automatically raises `DeferredRun` so the scheduler defers the run without consuming a failure retry. Any other non-`"success"` status raises a `RuntimeError` so the failure is recorded and retried according to policy.

## Execution context, locking, and timeouts

### Execution context and idempotency

When `execution_context` is accepted (or `with_context=True` is set), the handler receives a dictionary with metadata for the current attempt:

| Key | Type | Meaning |
|---|---|---|
| `slot` | `str` | Canonical UTC slot identifier for calendar runs (or a unique `manual:...` slot for **Run now**) |
| `idempotency_key` | `str` | Stable key combining `schedule_id` and `slot` across retries of the same occurrence |
| `attempt` | `int` | 1-based attempt number for this slot (`1` through `3` for automatic retries) |
| `operation_id` | `str` | Correlation ID for structured logs and operation tracking |

Scheduled execution is **at-least-once** across process crashes. Although BSM persists database claims before starting a handler, an external crash mid-execution can trigger a retry on startup. Use `execution_context["idempotency_key"]` to avoid repeating external side effects (such as sending duplicate webhooks or creating duplicate external records).

### Server locks and cooperative deferral

- **`requires_server_lock=True` (default):** Acquires the target server's `operation_lock` before invoking your handler. If an interactive operation is already holding or waiting on the lock, the scheduler defers the scheduled run for 1 minute without counting it as a failed attempt.
- **`requires_server_lock=False`:** Runs the handler without acquiring the server's `operation_lock` upfront. Use this for read-only log scans or lightweight console commands (`server.send_command`). Core API methods called inside your handler still enforce their own internal locks when needed.

### Timeouts and cancellation

Plugin scheduled tasks default to `timeout_seconds=300` (configurable from `1` to `86400` seconds). Built-in long-running archive tasks use `timeout_seconds=None`.

Cancellation is cooperative:

- Do not swallow `asyncio.CancelledError`. Perform cleanup in `finally` blocks and let cancellation propagate.
- Avoid blocking synchronous I/O on the event loop; use `async` APIs so timeouts and plugin unload can cancel work promptly.

### Plugin lifecycle and availability

Scheduled task registrations are bound to your plugin's `(owner, generation)`. When a plugin is disabled, unloaded, or reloaded:

1. Old task registrations from the previous generation are invalidated automatically.
2. Administrator-created schedules that reference `<plugin_name>:<task>` are **retained** in the database and marked `available=False` (`Unavailable` in the UI) while the plugin is unloaded.
3. When the plugin loads again and re-registers `<plugin_name>:<task>`, existing schedules automatically become available and resume normal execution.

## Inspect schedules from a plugin

Plugins can read configured schedules, task availability, and recent run history through `self.api.scheduler.list_schedules`:

```python
from bedrock_server_manager.api.models import ListSchedulesRequest

response = await self.api.scheduler.list_schedules(
    ListSchedulesRequest(server_name="survival")
)
for schedule in response.schedules:
    self.logger.info(
        "Schedule %s (%s): enabled=%s, next_run=%s",
        schedule.schedule_id,
        schedule.task,
        schedule.enabled,
        schedule.next_run_at,
    )
```

Note that `save_schedule`, `delete_schedule`, and `control_schedule` are administrator-only operations (`expose_to_plugins=False`) and cannot be called by plugins. See [Scheduler plugin APIs](../../plugins/api/scheduler.md) for the full `ListSchedulesRequest` and `ListSchedulesResponse` contract.
