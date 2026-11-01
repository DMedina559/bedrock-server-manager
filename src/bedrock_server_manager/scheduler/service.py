"""Lifecycle-owned scheduler, unified task registry, and API task orchestration."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field, create_model

if TYPE_CHECKING:
    from ..api.models.scheduler import ListSchedulesResponse

from ..backups.contents import BackupComponents, BackupMode
from ..logging import RepeatedFailureReporter
from ..utils.threads import run_in_thread
from .engine import occurrences, signature
from .runner import DeferredRun, next_attempt, run_schedule

logger = logging.getLogger(__name__)

_TASK_ALIASES: dict[str, str] = {
    "backup": "backup:create",
    "verify": "backup:verify",
}


class BackupScheduleOptions(BaseModel):
    """Serializable options for scheduled server snapshot creation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    encrypted: bool | None = None
    mode: BackupMode | None = None
    components: BackupComponents | None = None


class VerifyScheduleOptions(BaseModel):
    """Serializable options for scheduled backup archive verification."""

    model_config = ConfigDict(extra="forbid", strict=True)

    minimum_age_hours: int = Field(default=168, ge=0, le=8760)


class EmptyScheduleOptions(BaseModel):
    """Options model for scheduled API tasks that take only server_name."""

    model_config = ConfigDict(extra="forbid", strict=True)


@dataclass(frozen=True)
class TaskDefinition:
    """Unified registration entry for built-in and plugin scheduled tasks."""

    name: str
    handler: Callable[..., Awaitable[Any]]
    owner: str = "application"
    generation: int = 0
    options_model: type[BaseModel] | None = None
    timeout_seconds: float | None = 300
    requires_server_lock: bool = True
    with_context: bool = False
    manage_server_lock: bool = True
    exclude_unset_options: bool = False
    reconcile_handler: Callable[[Any, str], Awaitable[bool]] | None = None
    options_validator: Callable[[Any, str, dict[str, Any]], None] | None = None
    description: str = ""
    api_method_name: str | None = None


def _derive_api_options_model(
    request_cls: type[BaseModel],
    default_options: dict[str, Any] | None = None,
) -> type[BaseModel]:
    """Build a schedule options Pydantic model from an APIRequest model."""
    fields: dict[str, Any] = {}
    defaults = default_options or {}
    for field_name, field_info in request_cls.model_fields.items():
        if field_name in {"server_name", "schedule_slot"}:
            continue
        annotation = field_info.annotation or Any
        if field_name in defaults:
            fields[field_name] = (
                annotation,
                Field(default=defaults[field_name], description=field_info.description),
            )
        elif field_info.is_required():
            fields[field_name] = (
                annotation,
                Field(..., description=field_info.description),
            )
        elif field_info.default_factory is not None:
            fields[field_name] = (
                annotation,
                Field(
                    default_factory=field_info.default_factory,
                    description=field_info.description,
                ),
            )
        else:
            fields[field_name] = (
                annotation,
                Field(
                    default=field_info.default,
                    description=field_info.description,
                ),
            )
    if not fields:
        return EmptyScheduleOptions
    return create_model(
        f"{request_cls.__name__}ScheduleOptions",
        __config__=ConfigDict(extra="forbid", strict=True),
        **fields,
    )


class Scheduler:
    """Manage scheduled server tasks and the unified ``TaskDefinition`` registry."""

    def __init__(self, context):
        self._log_failures = RepeatedFailureReporter(logging.getLogger(__name__))
        self.context = context
        self.task = None
        self._jobs = {}
        self._slots = asyncio.Semaphore(4)
        self._limit = 4
        self._interval = 60
        self._wake = asyncio.Event()
        self._handlers: dict[str, TaskDefinition] = {}
        self._settings_lock = asyncio.Lock()
        self._migration_lock = asyncio.Lock()
        self.last_tick_at = None
        self._last_tick_monotonic = None
        self.last_error_type = None
        self._register_builtin_tasks()

    @property
    def repository(self):
        return self.context.storage.scheduler_repo

    def resolve_task_name(self, name: str, *, warn_deprecated: bool = False) -> str:
        """Resolve a task name, normalizing legacy aliases when present."""
        canonical = _TASK_ALIASES.get(name)
        if canonical is not None:
            if warn_deprecated:
                logger.warning(
                    "Scheduled task '%s' is deprecated and will be removed in a future version; use '%s' instead.",
                    name,
                    canonical,
                )
            return canonical
        return name

    def get_task_definition(
        self, name: str, *, warn_deprecated: bool = False
    ) -> TaskDefinition | None:
        """Return the active ``TaskDefinition`` for ``name`` if available."""
        canonical = self.resolve_task_name(name, warn_deprecated=warn_deprecated)
        entry = self._handlers.get(canonical)
        if entry is None:
            return None
        if entry.owner != "application":
            try:
                self.context.events.check_owner(entry.owner, entry.generation)
            except RuntimeError:
                self._handlers.pop(canonical, None)
                return None
        return entry

    def register(
        self,
        name: str,
        handler: Callable[..., Awaitable[Any]],
        *,
        owner: str = "application",
        generation: int = 0,
        options_model: type[BaseModel] | None = None,
        timeout_seconds: float | None = 300,
        requires_server_lock: bool = True,
        with_context: bool = False,
        manage_server_lock: bool | None = None,
        exclude_unset_options: bool = False,
        reconcile_handler: Callable[[Any, str], Awaitable[bool]] | None = None,
        options_validator: Callable[[Any, str, dict[str, Any]], None] | None = None,
        description: str = "",
        api_method_name: str | None = None,
    ) -> TaskDefinition:
        """Register an async scheduled task handler in the unified task registry."""
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("Scheduled task handlers must be async functions")

        if owner.startswith("plugin:"):
            plugin_prefix = owner.removeprefix("plugin:")
            if ":" not in name and re.fullmatch(r"[a-zA-Z0-9_.-]+", name):
                name = f"{plugin_prefix}:{name}"

        if (
            not re.fullmatch(r"[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+", name)
            or len(name) > 160
        ):
            raise ValueError(
                "Scheduled task names require a namespace and name within 160 characters"
            )
        if owner.startswith("plugin:") and not name.startswith(
            owner.removeprefix("plugin:") + ":"
        ):
            raise ValueError("Scheduled task names must use the plugin namespace")
        if name in self._handlers and self.available(name):
            raise ValueError("Scheduled task is already registered")

        if options_model is None:
            try:
                sig = inspect.signature(handler)
                opt_param = sig.parameters.get("options")
                if (
                    opt_param is not None
                    and inspect.isclass(opt_param.annotation)
                    and issubclass(opt_param.annotation, BaseModel)
                ):
                    options_model = opt_param.annotation
                if not with_context and "execution_context" in sig.parameters:
                    with_context = True
            except (ValueError, TypeError):
                pass

        if options_model is not None and (
            not inspect.isclass(options_model)
            or not issubclass(options_model, BaseModel)
        ):
            raise TypeError("Task options_model must be a Pydantic model class")
        if timeout_seconds is not None and (
            type(timeout_seconds) not in (int, float)
            or not 1 <= timeout_seconds <= 86400
        ):
            raise ValueError("Task timeout must be from 1 through 86400 seconds")
        if options_model is not None:
            options_model.model_json_schema()

        effective_manage_lock = (
            requires_server_lock if manage_server_lock is None else manage_server_lock
        )
        definition = TaskDefinition(
            name=name,
            handler=handler,
            owner=owner,
            generation=generation,
            options_model=options_model,
            timeout_seconds=timeout_seconds,
            requires_server_lock=requires_server_lock,
            with_context=with_context,
            manage_server_lock=effective_manage_lock,
            exclude_unset_options=exclude_unset_options,
            reconcile_handler=reconcile_handler,
            options_validator=options_validator,
            description=description,
            api_method_name=api_method_name,
        )
        self._handlers[name] = definition
        return definition

    def register_api_task(
        self,
        name: str,
        api_function: Callable[..., Any] | str,
        *,
        owner: str = "application",
        generation: int = 0,
        options_model: type[BaseModel] | None = None,
        default_options: dict[str, Any] | None = None,
        slot_field: str | None = None,
        timeout_seconds: float | None = 300,
        requires_server_lock: bool = True,
        manage_server_lock: bool = False,
        exclude_unset_options: bool = True,
        reconcile_handler: Callable[[Any, str], Awaitable[bool]] | None = None,
        options_validator: Callable[[Any, str, dict[str, Any]], None] | None = None,
        description: str = "",
        failure_message: str | None = None,
    ) -> TaskDefinition:
        """Register an API method to run as a scheduled task."""
        from importlib import import_module

        from ..api.contract import get_contract
        from ..plugins.api_bridge import _api_methods, _api_registry

        import_module("bedrock_server_manager.api")

        resolved_api_name: str | None = None
        resolved_domain: str | None = None
        resolved_method: str | None = None
        target_callable: Callable[..., Any] | None = None
        request_cls: type[BaseModel] | None = None

        if isinstance(api_function, str):
            if "." in api_function:
                domain_part, method_part = api_function.split(".", 1)
                reg_name = (
                    _api_methods().get(domain_part, {}).get(method_part, method_part)
                )
                entry = _api_registry.get(reg_name)
                if entry is None:
                    raise ValueError(f"Unknown API method '{api_function}'")
                resolved_api_name = reg_name
                resolved_domain = domain_part
                resolved_method = method_part
                target_callable = entry[0]
            else:
                entry = _api_registry.get(api_function)
                if entry is None:
                    raise ValueError(f"Unknown API method '{api_function}'")
                resolved_api_name = api_function
                resolved_domain = entry[4]
                resolved_method = next(
                    (
                        m
                        for m, r in _api_methods().get(resolved_domain, {}).items()
                        if r == api_function
                    ),
                    api_function,
                )
                target_callable = entry[0]
        elif callable(api_function):
            target_callable = api_function
            unwrapped = getattr(api_function, "__wrapped__", api_function)
            for reg_name, entry in _api_registry.items():
                if entry[0] is unwrapped or entry[0] is api_function:
                    resolved_api_name = reg_name
                    resolved_domain = entry[4]
                    resolved_method = next(
                        (
                            m
                            for m, r in _api_methods().get(resolved_domain, {}).items()
                            if r == reg_name
                        ),
                        reg_name,
                    )
                    break
        else:
            raise TypeError("api_function must be a callable or registered API name")

        if target_callable is not None:
            unwrapped = getattr(target_callable, "__wrapped__", target_callable)
            try:
                contract = get_contract(unwrapped) or get_contract(target_callable)
            except (TypeError, NameError):
                contract = None
            if contract is not None:
                request_cls = contract[0]
            else:
                try:
                    sig = inspect.signature(target_callable)
                    first_param = next(iter(sig.parameters.values()), None)
                    if (
                        first_param is not None
                        and inspect.isclass(first_param.annotation)
                        and issubclass(first_param.annotation, BaseModel)
                    ):
                        request_cls = first_param.annotation
                except (ValueError, TypeError):
                    pass

        if options_model is None and request_cls is not None:
            options_model = _derive_api_options_model(request_cls, default_options)

        doc = description
        if not doc and target_callable is not None:
            raw_doc = inspect.getdoc(target_callable) or ""
            doc = raw_doc.strip().split("\n")[0] if raw_doc else ""

        err_msg = failure_message or f"Scheduled task '{name}' did not complete"

        async def _api_handler(
            *,
            server_name: str,
            options: dict[str, Any],
            execution_context: dict[str, Any] | None = None,
        ) -> Any:
            payload: dict[str, Any] = dict(default_options or {})
            payload.update(options)
            if request_cls is None or "server_name" in request_cls.model_fields:
                payload["server_name"] = server_name
            if slot_field and execution_context and "slot" in execution_context:
                payload[slot_field] = execution_context["slot"]

            if (
                isinstance(api_function, str)
                and resolved_domain is not None
                and resolved_method is not None
            ):
                namespace = getattr(self.context.api, resolved_domain)
                api_call = getattr(namespace, resolved_method)
                result = api_call(request=payload)
            else:
                assert target_callable is not None
                sig = inspect.signature(target_callable)
                call_kwargs: dict[str, Any] = {}
                if "app_context" in sig.parameters:
                    call_kwargs["app_context"] = self.context
                if "plugin_name" in sig.parameters and owner.startswith("plugin:"):
                    call_kwargs["plugin_name"] = owner.removeprefix("plugin:")
                if "request" in sig.parameters:
                    result = target_callable(request=payload, **call_kwargs)
                else:
                    result = target_callable(payload, **call_kwargs)

            if inspect.isawaitable(result):
                result = await result

            if hasattr(result, "status"):
                status = getattr(result, "status")
                detail = getattr(result, "message", None)
                if status == "skipped":
                    try:
                        server = self.context.get_server(
                            server_name, require_installation=False
                        )
                    except Exception:
                        server = None
                    if (server is not None and server.operation_lock.locked()) or (
                        isinstance(detail, str)
                        and "already in progress" in detail.lower()
                    ):
                        raise DeferredRun(
                            "Scheduled task yielded to active server operation"
                        )
                if status != "success":
                    raise RuntimeError(f"{err_msg}: {detail}" if detail else err_msg)
            return result

        return self.register(
            name,
            _api_handler,
            owner=owner,
            generation=generation,
            options_model=options_model,
            timeout_seconds=timeout_seconds,
            requires_server_lock=requires_server_lock,
            with_context=bool(slot_field),
            manage_server_lock=manage_server_lock,
            exclude_unset_options=exclude_unset_options,
            reconcile_handler=reconcile_handler,
            options_validator=options_validator,
            description=doc,
            api_method_name=resolved_api_name
            or getattr(target_callable, "__name__", str(api_function)),
        )

    def _register_builtin_tasks(self) -> None:
        """Register core backup/restore and server management APIs into the scheduler."""

        def _validate_backup_options(
            scheduler: Scheduler, server_name: str, options: dict[str, Any]
        ) -> None:
            from ..api.models.backup_restore import CreateSnapshotRequest
            from ..backups.selection import selection
            from ..error import BackupRestoreError, UserInputError

            allowed = {"encrypted", "mode", "components"}
            if set(options) - allowed:
                raise UserInputError("Unknown scheduled task option")
            try:
                CreateSnapshotRequest(server_name=server_name or "all", **options)
                selection(
                    scheduler.context.settings,
                    options.get("mode"),
                    options.get("components"),
                )
            except (ValueError, TypeError, BackupRestoreError) as error:
                raise UserInputError(
                    "Invalid backup content or encryption options"
                ) from error

        async def _reconcile_backup_slot(server: Any, slot: str) -> bool:
            async with server.operation_lock:

                def _has_slot_archive() -> bool:
                    value = server.backups.catalog.load()
                    return any(
                        item.get("schedule_slot") == slot
                        and (server.backups.catalog.directory / filename).is_file()
                        for filename, item in value["archives"].items()
                    )

                return await run_in_thread(_has_slot_archive)

        def _validate_verify_options(
            scheduler: Scheduler, server_name: str, options: dict[str, Any]
        ) -> None:
            from ..error import UserInputError

            allowed = {"minimum_age_hours"}
            if set(options) - allowed:
                raise UserInputError("Unknown scheduled task option")
            age = options.get("minimum_age_hours", 168)
            if type(age) is not int or not 0 <= age <= 8760:
                raise UserInputError(
                    "Verification age must be an integer from 0 to 8760"
                )

        async def _verify_backups_handler(
            *, server_name: str, options: dict[str, Any]
        ) -> None:
            server = self.context.get_server(server_name, require_installation=False)
            age = options.get("minimum_age_hours", 168)
            failed = 0
            for item in await server.backups.list_snapshots():
                if server.operation_lock.waiting:
                    raise DeferredRun("Verification yielded to interactive work")
                checked = item.verification.verified_at
                if (
                    item.verification.status != "verified"
                    or not checked
                    or datetime.now(timezone.utc) - datetime.fromisoformat(checked)
                    >= timedelta(hours=age)
                ):
                    try:
                        await server.backups.verify_snapshot(item.backup_id)
                    except Exception as error:
                        self._log_failures.report(
                            "verification", "Scheduler %s failed: %s", error
                        )
                        failed += 1
            if failed:
                raise RuntimeError(
                    "Some scheduled archive verifications failed; inspect backup health"
                )

        self.register_api_task(
            "backup:create",
            "backup_restore.create_server_backup",
            owner="application",
            options_model=BackupScheduleOptions,
            default_options={"purpose": "scheduled"},
            slot_field="schedule_slot",
            timeout_seconds=None,
            requires_server_lock=True,
            manage_server_lock=False,
            exclude_unset_options=True,
            reconcile_handler=_reconcile_backup_slot,
            options_validator=_validate_backup_options,
            description="Create a scheduled server snapshot archive.",
            failure_message="Scheduled backup did not complete",
        )
        self.register(
            "backup:verify",
            _verify_backups_handler,
            owner="application",
            options_model=VerifyScheduleOptions,
            timeout_seconds=None,
            requires_server_lock=True,
            manage_server_lock=False,
            exclude_unset_options=True,
            options_validator=_validate_verify_options,
            description="Verify snapshot archive integrity for backups older than minimum_age_hours.",
        )
        self.register_api_task(
            "backup:prune",
            "backup_restore.prune_old_backups",
            owner="application",
            timeout_seconds=None,
            requires_server_lock=True,
            manage_server_lock=False,
            description="Prune old backups according to server retention policies.",
        )
        self.register_api_task(
            "backup:world",
            "backup_restore.backup_world",
            owner="application",
            timeout_seconds=None,
            requires_server_lock=True,
            manage_server_lock=False,
            description="Back up the server world directory.",
        )
        self.register_api_task(
            "backup:all",
            "backup_restore.backup_all",
            owner="application",
            timeout_seconds=None,
            requires_server_lock=True,
            manage_server_lock=False,
            description="Back up server world and configuration files.",
        )
        self.register_api_task(
            "server:start",
            "server.start",
            owner="application",
            requires_server_lock=True,
            manage_server_lock=False,
            description="Start the Bedrock server.",
        )
        self.register_api_task(
            "server:stop",
            "server.stop",
            owner="application",
            requires_server_lock=True,
            manage_server_lock=False,
            description="Stop the Bedrock server.",
        )
        self.register_api_task(
            "server:restart",
            "server.restart",
            owner="application",
            requires_server_lock=True,
            manage_server_lock=False,
            description="Restart the Bedrock server.",
        )
        self.register_api_task(
            "server:send_command",
            "server.send_command",
            owner="application",
            requires_server_lock=False,
            manage_server_lock=False,
            description="Send a console command to a running Bedrock server.",
        )
        self.register_api_task(
            "world:export",
            "world.export_world",
            owner="application",
            timeout_seconds=None,
            requires_server_lock=True,
            manage_server_lock=False,
            description="Export the active server world to a .mcworld archive.",
        )

    def remove_owner(self, owner):
        """Remove all scheduled task definitions registered by ``owner``."""
        for name, entry in list(self._handlers.items()):
            if entry.owner == owner:
                self._handlers.pop(name, None)

    def available(self, name: str) -> bool:
        """Return whether ``name`` resolves to an active registered task."""
        return self.get_task_definition(name) is not None

    async def configurations(self, server_name=None):
        async with self._migration_lock:
            return await self._configurations(server_name)

    async def _configurations(self, server_name=None):
        rows = await self.repository.list()
        return {
            name: (config, state, server)
            for name, config, state, server in rows
            if server_name is None or config["server_name"] == server_name
        }

    async def snapshot(self, server_name=None) -> "ListSchedulesResponse":
        from ..api.models.scheduler import ListSchedulesResponse, ScheduleEntry

        entries = []
        definitions = await self.configurations(server_name)
        histories = await self.repository.histories(definitions)
        now = datetime.now(timezone.utc)
        for name, (config, record, legacy) in definitions.items():
            try:
                self.context.get_server(
                    config["server_name"], require_installation=False
                )
                available = self.available(config["task"])
            except Exception as error:
                self._log_failures.report(
                    "availability", "Scheduler %s failed: %s", error
                )
                available = False
            try:
                slots = occurrences(
                    config, config["server_name"], datetime.now(timezone.utc)
                )
            except (ValueError, KeyError):
                slots, available = [], False
            future = [slot for slot in slots if slot > datetime.now(timezone.utc)]
            entries.append(
                ScheduleEntry(
                    schedule_id=name,
                    configuration=config,
                    available=available,
                    legacy=bool(legacy),
                    next_run_at=(
                        future[0].isoformat()
                        if future and config["enabled"] and available
                        else None
                    ),
                    last_status=record.get("status"),
                    last_success_at=record.get("last_success_at"),
                    last_error=record.get("error"),
                    attempts=record.get("attempts", 0),
                    runs=histories.get(name, []),
                    revision=signature(config),
                    next_attempt_at=next_attempt(config, record, now, name),
                    retry_exhausted=(
                        record.get("attempts", 0) >= 3
                        and record.get("status") in ("failed", "interrupted")
                    )
                    or record.get("blocked_reason") == "retry_expired",
                    blocked_reason=record.get("blocked_reason"),
                    last_evaluated_at=record.get("last_evaluated_at"),
                )
            )
        available_handlers = [
            name for name in list(self._handlers) if self.available(name)
        ]
        types = sorted(set(available_handlers) | set(_TASK_ALIASES))
        from ..utils.timezones import schedule_timezones, timezone_database_available

        return ListSchedulesResponse(
            schedules=entries,
            task_types=types,
            task_definitions={
                name: {
                    "options_schema": (
                        entry.options_model.model_json_schema()
                        if entry.options_model
                        else None
                    ),
                    "timeout_seconds": entry.timeout_seconds,
                    "requires_server_lock": entry.requires_server_lock,
                    "with_context": entry.with_context,
                    "description": entry.description,
                    "owner": entry.owner,
                }
                for name, entry in list(self._handlers.items())
                if self.available(name)
            },
            server_time=datetime.now(timezone.utc).isoformat(),
            host_timezone=datetime.now().astimezone().tzname(),
            timezone_database_available=timezone_database_available(),
            timezones=await run_in_thread(schedule_timezones),
        )

    async def save(self, request):
        from ..error import UserInputError

        self.context.get_server(
            request.configuration.server_name, require_installation=False
        )
        raw_task = request.configuration.task
        canonical_task = self.resolve_task_name(raw_task, warn_deprecated=True)
        if canonical_task != raw_task:
            request = request.model_copy(
                update={
                    "configuration": request.configuration.model_copy(
                        update={"task": canonical_task}
                    )
                }
            )
        options = request.configuration.options
        definition = self.get_task_definition(canonical_task, warn_deprecated=False)
        if definition is not None:
            if definition.options_validator is not None:
                definition.options_validator(
                    self, request.configuration.server_name, options
                )
            elif definition.options_model is not None:
                try:
                    from ..services.plugin_service import _json_settings

                    validated_model = definition.options_model.model_validate_json(
                        json.dumps(options), strict=True
                    )
                    if definition.exclude_unset_options:
                        checked = json.loads(
                            validated_model.model_dump_json(exclude_unset=True)
                        )
                    else:
                        checked = _json_settings(validated_model)
                except ValueError as error:
                    raise UserInputError(
                        "Invalid scheduled plugin task options"
                        if definition.owner.startswith("plugin:")
                        else "Invalid scheduled task options"
                    ) from error
                request = request.model_copy(
                    update={
                        "configuration": request.configuration.model_copy(
                            update={"options": checked}
                        )
                    }
                )
        async with self._settings_lock:
            rows = await self.configurations()
            previous = rows.get(request.schedule_id)
            configuration = request.configuration
            if "timezone" not in configuration.model_fields_set:
                zone = (
                    previous[0]["timezone"]
                    if previous
                    else self.context.settings.get("general.timezone", "UTC")
                )
                configuration = configuration.model_copy(update={"timezone": zone})
            if previous is None and len(rows) >= 500:
                raise UserInputError("At most 500 schedules may be configured")
            await self.repository.save(request.schedule_id, configuration.model_dump())
            self._wake.set()

    async def delete(self, name):
        async with self._settings_lock:
            previous = (await self.configurations()).get(name)
            if previous and previous[1].get("status") == "running":
                from ..error import UserInputError

                raise UserInputError(
                    "Wait for the active schedule run to finish before removing it"
                )
            await self.repository.delete(name)
            self._wake.set()

    async def execute(self, name, config, server, slot, execution=None):
        import time
        from uuid import uuid4

        from ..events.bus import current_correlation_id

        started = time.monotonic()
        failure = None
        run_id = uuid4().hex
        definition = self.get_task_definition(config["task"])
        owner = (
            definition.owner
            if definition is not None
            else (
                "application"
                if ":" not in config["task"]
                else "plugin:" + config["task"].split(":", 1)[0]
            )
        )
        with self.context.events.operations.scope(
            "scheduler.run", server_name=server.server_name
        ) as operation:
            await self.repository.run(
                name,
                slot,
                run_id=run_id,
                status="running",
                correlation_id=current_correlation_id(),
            )
            try:
                await self._execute(config, server, slot, execution=execution)
            except BaseException as error:
                failure = error
                await self.repository.run(
                    name,
                    slot,
                    run_id=run_id,
                    status=(
                        "interrupted"
                        if isinstance(error, asyncio.CancelledError)
                        else "deferred" if isinstance(error, DeferredRun) else "failed"
                    ),
                    error="Scheduled task did not complete; inspect diagnostics and logs.",
                )
                raise
            else:
                await self.repository.run(name, slot, run_id=run_id, status="completed")
            finally:
                if self.context._diagnostics is not None:
                    self.context._diagnostics.record(
                        "scheduler",
                        config["task"],
                        started=started,
                        error=failure,
                        correlation_id=current_correlation_id(),
                        operation_id=operation.snapshot.operation_id,
                        owner=owner,
                    )

    async def _execute(self, config, server, slot, *, execution=None):
        definition = self.get_task_definition(config["task"], warn_deprecated=True)
        if definition is None:
            raise RuntimeError("Scheduled task handler is unavailable")

        manager = self.context._plugin_manager
        current = asyncio.current_task()
        tasks = (
            manager.plugin_tasks.setdefault(
                definition.owner.removeprefix("plugin:"), []
            )
            if manager and definition.owner.startswith("plugin:")
            else []
        )
        if current is not None and definition.owner.startswith("plugin:"):
            tasks.append(current)
        try:
            from ..events.bus import current_correlation_id

            options = dict(config.get("options", {}))
            if definition.options_model is not None:
                from ..services.plugin_service import _json_settings

                validated = definition.options_model.model_validate_json(
                    json.dumps(options), strict=True
                )
                if definition.exclude_unset_options:
                    options = json.loads(validated.model_dump_json(exclude_unset=True))
                else:
                    options = _json_settings(validated)
            kwargs: dict[str, Any] = {
                "server_name": server.server_name,
                "options": options,
            }
            if definition.with_context:
                kwargs["execution_context"] = {
                    "slot": slot,
                    "idempotency_key": slot,
                    "attempt": (execution or {}).get("attempts", 1),
                    "correlation_id": current_correlation_id(),
                }
            async with (
                asyncio.timeout(definition.timeout_seconds)
                if definition.timeout_seconds is not None
                else nullcontext()
            ):
                async with (
                    server.operation_lock
                    if definition.manage_server_lock
                    else nullcontext()
                ):
                    await definition.handler(**kwargs)
        finally:
            if current in tasks:
                tasks.remove(current)

    async def _maintain_server(self, name, definitions=None):
        server = self.context.get_server(name, require_installation=False)
        async with self._slots:
            performed = False
            entries = (
                definitions
                if definitions is not None
                else await self.configurations(name)
            )
            for identifier, (config, state, legacy) in entries.items():
                try:
                    definition = self.get_task_definition(config["task"])
                    if definition is None:
                        raise ValueError("handler_unavailable")
                    from ..utils.timezones import resolve_timezone

                    await run_in_thread(resolve_timezone, config["timezone"])

                    if state.get("blocked_reason") == "preparation_failed":

                        def repaired(current, record):
                            if current == config:
                                record.update(blocked_reason=None, error=None)

                        await self.repository.mutate(identifier, repaired)

                    async def execute(
                        slot,
                        execution,
                        _id=identifier,
                        _cfg=config,
                    ):
                        await self.execute(_id, _cfg, server, slot, execution)

                    async def reconcile(slot, _def=definition):
                        return await _def.reconcile_handler(server, slot)

                    performed = (
                        await run_schedule(
                            self.repository,
                            identifier,
                            config,
                            server,
                            execute,
                            reconcile=(
                                reconcile
                                if definition.reconcile_handler is not None
                                else None
                            ),
                            check_contention=definition.requires_server_lock,
                        )
                        or performed
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:

                    def blocked(current, record):
                        if current == config and not record.get("lease"):
                            record.update(
                                blocked_reason="preparation_failed",
                                error="Scheduled work could not be prepared; inspect diagnostics and logs.",
                                last_evaluated_at=datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            )

                    await self.repository.mutate(identifier, blocked)
                    logging.getLogger(__name__).warning(
                        "Scheduled work needs attention for '%s'.",
                        identifier,
                        exc_info=True,
                    )
            if not performed:
                try:
                    await server.backups.maintain_backups()
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Backup maintenance failed for '%s'.", name, exc_info=True
                    )

    async def control(self, request):
        """Explicit controls are revision checked and never replay an active run."""
        from uuid import uuid4

        from ..error import UserInputError

        async with self._settings_lock:
            rows = await self.configurations()
            previous = rows.get(request.schedule_id)
            if previous is None:
                raise UserInputError("Schedule does not exist")
            config, _, _ = previous
            if request.revision is not None and signature(config) != request.revision:
                raise UserInputError("Schedule changed; refresh before trying again")
            if request.action in ("pause", "resume"):
                configuration = dict(config, enabled=request.action == "resume")
                await self.repository.save(request.schedule_id, configuration)
                self._wake.set()
                return
            else:
                if not self.available(config["task"]):
                    raise UserInputError("Scheduled task handler is unavailable")

                self.context.get_server(
                    config["server_name"], require_installation=False
                )

                def mutate(current, state):
                    if current != config or state.get("lease"):
                        raise UserInputError(
                            "Schedule changed or is already running; refresh first"
                        )
                    if state.get("requested_slot"):
                        raise UserInputError("A run is already queued")
                    if request.action == "retry":
                        if state.get("status") not in (
                            "failed",
                            "interrupted",
                            "deferred",
                        ) or not state.get("slot"):
                            raise UserInputError("No failed run is available to retry")
                        state.update(attempts=0, next_retry_at=None)
                        state["requested_slot"] = state["slot"]
                    else:
                        state["requested_slot"] = "manual:" + uuid4().hex

                await self.repository.mutate(request.schedule_id, mutate)
                self._wake.set()
                return

    async def diagnostic_snapshot(self):
        import time

        from ..diagnostics.models import PluginValues, SchedulerDiagnostics
        from ..utils.timezones import timezone_database_available

        entries = self.context.state.scheduler.records
        enabled = [
            (config, state)
            for config, state, legacy in entries.values()
            if config["enabled"]
        ]
        from ..utils.timezones import resolve_timezone

        def unavailable(config):
            if (
                not self.available(config["task"])
                or config["server_name"] not in self.context.state.servers.servers
            ):
                return True
            try:
                resolve_timezone(config["timezone"])
            except (ValueError, KeyError):
                return True
            return False

        missing = sum(unavailable(config) for config, state in enabled)
        observation = SchedulerDiagnostics(
            running=self.task is not None and not self.task.done(),
            schedules=len(entries),
            enabled=len(enabled),
            active_jobs=len(self._jobs),
            failed=sum(
                (
                    state.get("status") in ("failed", "interrupted")
                    or state.get("blocked_reason")
                    in ("preparation_failed", "retry_exhausted", "retry_expired")
                )
                for config, state in enabled
            ),
            unavailable=missing,
            last_tick_at=self.last_tick_at,
            tick_age_seconds=(
                max(0.0, time.monotonic() - self._last_tick_monotonic)
                if self._last_tick_monotonic is not None
                else None
            ),
            last_error_type=self.last_error_type,
            timezone_database_available=timezone_database_available(),
        )

        # Keep the established metadata wire contract for existing 4.0 clients.
        return PluginValues(
            health=(
                "ok"
                if self.check_health()
                and not observation.failed
                and not observation.unavailable
                and observation.timezone_database_available
                else "degraded"
            ),
            values={
                **{
                    key: value
                    for key, value in observation.model_dump().items()
                    if key not in ("kind", "last_error_type")
                },
                "running_executions": sum(
                    bool(state.get("lease"))
                    for config, state, legacy in entries.values()
                ),
                "concurrency_limit": self._limit,
                "queued_workers": max(0, len(self._jobs) - self._limit),
            },
            units={"tick_age_seconds": "seconds"},
        )

    def check_health(self):
        import time

        return (
            self.task is not None
            and not self.task.done()
            and self._last_tick_monotonic is not None
            and time.monotonic() - self._last_tick_monotonic < 180
            and self.last_error_type is None
        )

    def start(self):
        if self.task is None or self.task.done():
            self._limit = self.context.settings.get(
                "scheduler.max_concurrent_servers", 4
            )
            self._interval = self.context.settings.get(
                "scheduler.poll_interval_seconds", 60
            )
            self._slots = asyncio.Semaphore(self._limit)
            self.task = asyncio.create_task(self._run(), name="scheduler")

    def _finished(self, name, task):
        if self._jobs.get(name) is task:
            self._jobs.pop(name, None)
        self.context.state.runtime.scheduler["active_jobs"] = len(self._jobs)
        if not task.cancelled():
            error = task.exception()
            if error is not None:
                logging.getLogger(__name__).warning(
                    "Scheduler worker failed for '%s': %s", name, type(error).__name__
                )

    async def _run(self):
        import time

        from ..services.lifecycle import LifecyclePhase

        try:
            recovered = False
            while True:
                if self.context.lifecycle_phase != LifecyclePhase.READY:
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=0.1)
                    except TimeoutError:
                        pass
                    self._wake.clear()
                    continue
                if not recovered:
                    await self.repository.recover()
                    recovered = True
                self.last_tick_at = time.time()
                self._last_tick_monotonic = time.monotonic()
                self.last_error_type = None
                # Publish runtime observations independently from persistent definitions.
                self.context.state.runtime.scheduler = {
                    "running": True,
                    "last_tick_at": self.last_tick_at,
                    "active_jobs": len(self._jobs),
                    "last_error_type": None,
                }
                names = set(self.context.state.servers.servers)
                for name, task in list(self._jobs.items()):
                    if name not in names:
                        task.cancel()
                definitions = await self.configurations()
                grouped = {name: {} for name in names}
                for identifier, entry in definitions.items():
                    if entry[0]["server_name"] in grouped:
                        grouped[entry[0]["server_name"]][identifier] = entry
                for name in sorted(names):
                    if name not in self._jobs:
                        task = asyncio.create_task(
                            self._maintain_server(name, grouped[name]),
                            name=f"scheduler:{name}",
                        )
                        self._jobs[name] = task
                        task.add_done_callback(
                            lambda done, name=name: self._finished(name, done)
                        )
                self.context.state.runtime.scheduler["active_jobs"] = len(self._jobs)
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=self._interval)
                except TimeoutError:
                    pass
                self._wake.clear()
        except Exception as error:
            self.last_error_type = type(error).__name__
            logging.getLogger(__name__).exception("Scheduler loop stopped unexpectedly")
            raise
        finally:
            self.context.state.runtime.scheduler = {
                "running": False,
                "last_tick_at": self.last_tick_at,
                "active_jobs": 0,
                "last_error_type": self.last_error_type,
            }
            tasks = list(self._jobs.values())
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def shutdown(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        for name, entry in list(self._handlers.items()):
            if entry.owner != "application":
                self._handlers.pop(name, None)
