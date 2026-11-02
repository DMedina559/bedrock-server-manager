"""Lifecycle-owned scheduler, task orchestration, and background worker loop."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..api.models.scheduler import ListSchedulesResponse

from ..logging import RepeatedFailureReporter
from ..utils.threads import run_in_thread
from .builtin import register_builtin_tasks
from .engine import occurrences, signature
from .runner import DeferredRun, next_attempt, run_schedule
from .tasks import TaskRegistry

logger = logging.getLogger(__name__)


class Scheduler:
    """Manage scheduled server tasks and the background execution loop."""

    def __init__(self, context):
        self._log_failures = RepeatedFailureReporter(logging.getLogger(__name__))
        self.context = context
        self.task = None
        self._jobs = {}
        self._slots = asyncio.Semaphore(4)
        self._limit = 4
        self._interval = 60
        self._wake = asyncio.Event()
        self.tasks = TaskRegistry(context)
        self._handlers = self.tasks.handlers
        self._settings_lock = asyncio.Lock()
        self._migration_lock = asyncio.Lock()
        self.last_tick_at = None
        self._last_tick_monotonic = None
        self.last_error_type = None
        self._register_builtin_tasks()

    @property
    def repository(self):
        return self.context.storage.scheduler_repo

    def _register_builtin_tasks(self) -> None:
        """Register core backup/restore and server management APIs into the scheduler."""
        register_builtin_tasks(self)

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
                available = self.tasks.available(config["task"])
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
            name for name in list(self._handlers) if self.tasks.available(name)
        ]
        types = sorted(available_handlers)
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
                if self.tasks.available(name)
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
        task = request.configuration.task
        options = request.configuration.options
        definition = self.tasks.get_task_definition(task)
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
        definition = self.tasks.get_task_definition(config["task"])
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
        definition = self.tasks.get_task_definition(config["task"])
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
                    definition = self.tasks.get_task_definition(config["task"])
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
                if not self.tasks.available(config["task"]):
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
                not self.tasks.available(config["task"])
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
