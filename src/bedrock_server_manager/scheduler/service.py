"""Lifecycle-owned scheduler, task registry, and backup maintenance orchestration."""

import asyncio
import inspect
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.models.scheduler import ListSchedulesResponse

from datetime import datetime, timezone

from ..utils.threads import run_in_thread
from .engine import occurrences, run_due


class Scheduler:
    def __init__(self, context):
        self.context = context
        self.task = None
        self._jobs = {}
        self._slots = asyncio.Semaphore(4)
        self._handlers = {}
        self._settings_lock = asyncio.Lock()
        self._migration_lock = asyncio.Lock()
        self.last_tick_at = None
        self._last_tick_monotonic = None
        self.last_error_type = None

    @property
    def repository(self):
        return self.context.storage.scheduler_repo

    def register(self, name, handler, *, owner, generation):
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("Scheduled task handlers must be async functions")
        import re

        if (
            not re.fullmatch(r"[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+", name)
            or len(name) > 160
        ):
            raise ValueError(
                "Scheduled task names require a namespace and name within 160 characters"
            )
        if not name.startswith(owner.removeprefix("plugin:") + ":"):
            raise ValueError("Scheduled task names must use the plugin namespace")
        if name in self._handlers and self.available(name):
            raise ValueError("Scheduled task is already registered")
        self._handlers[name] = (handler, owner, generation)

    def remove_owner(self, owner):
        for name, entry in list(self._handlers.items()):
            if entry[1] == owner:
                self._handlers.pop(name, None)

    def available(self, name):
        if name in ("backup", "verify"):
            return True
        entry = self._handlers.get(name)
        if entry is None:
            return False
        try:
            self.context.events.check_owner(entry[1], entry[2])
        except RuntimeError:
            self._handlers.pop(name, None)
            return False
        return True

    async def configurations(self, server_name=None):
        async with self._migration_lock:
            return await self._configurations(server_name)

    async def _configurations(self, server_name=None):
        import hashlib

        # Existing settings remain a compatibility adapter. Stable IDs prevent duplication.
        rows = await self.repository.list()
        known = {row[0]: row for row in rows}
        for server, raw in self.context.settings.get("backups.schedules", {}).items():
            name = "backup-" + hashlib.sha256(server.encode()).hexdigest()[:20]
            config = raw.model_dump() if hasattr(raw, "model_dump") else raw
            config = dict(config, task="backup", server_name=server, options={})
            state = None
            if name not in known:
                try:
                    instance = self.context.get_server(
                        server, require_installation=False
                    )
                    async with instance.operation_lock:
                        value = await run_in_thread(instance.backups.catalog.load)
                    state = value.get("schedule", {})
                except Exception:
                    state = {}
            if name not in known or known[name][1] != config:
                await self.repository.save(
                    name, config, legacy_server=server, initial_state=state
                )
        legacy = self.context.settings.get("backups.schedules", {})
        for name, _, _, server in rows:
            if server and server not in legacy:
                await self.repository.delete(name)
        return {
            name: (config, state, server)
            for name, config, state, server in await self.repository.list()
            if server_name is None or config["server_name"] == server_name
        }

    async def snapshot(self, server_name=None) -> "ListSchedulesResponse":
        from ..api.models.scheduler import ListSchedulesResponse, ScheduleEntry

        entries = []
        for name, (config, record, legacy) in (
            await self.configurations(server_name)
        ).items():
            try:
                self.context.get_server(
                    config["server_name"], require_installation=False
                )
                available = self.available(config["task"])
            except Exception:
                record, available = {}, False
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
                    runs=await self.repository.history(name),
                )
            )
        types = ["backup", "verify"] + [
            name for name in list(self._handlers) if self.available(name)
        ]
        from ..utils.timezones import schedule_timezones, timezone_database_available

        return ListSchedulesResponse(
            schedules=entries,
            task_types=sorted(types),
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
        allowed = {
            "backup": {"encrypted", "mode", "components"},
            "verify": {"minimum_age_hours"},
        }.get(task)
        if allowed is not None and set(options) - allowed:
            raise UserInputError("Unknown scheduled task option")
        if task == "backup":
            from ..api.models.backup_restore import CreateSnapshotRequest
            from ..error import BackupRestoreError

            try:
                CreateSnapshotRequest(
                    server_name=request.configuration.server_name or "all", **options
                )
                from ..backups.selection import selection

                selection(
                    self.context.settings,
                    options.get("mode"),
                    options.get("components"),
                )
            except (ValueError, TypeError, BackupRestoreError) as error:
                raise UserInputError(
                    "Invalid backup content or encryption options"
                ) from error
        if task == "verify" and (
            type(options.get("minimum_age_hours", 168)) is not int
            or not 0 <= options.get("minimum_age_hours", 168) <= 8760
        ):
            raise UserInputError("Verification age must be an integer from 0 to 8760")
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
            if previous and previous[2]:
                if (
                    task != "backup"
                    or request.configuration.server_name != previous[2]
                    or options
                ):
                    raise UserInputError(
                        "Legacy schedules retain their backup task and server; create a new schedule instead"
                    )
                config = configuration.model_dump(
                    exclude={"task", "server_name", "options"}
                )
                legacy = self.context.settings.get("backups.schedules", {})
                legacy = {
                    k: v.model_dump() if hasattr(v, "model_dump") else v
                    for k, v in legacy.items()
                }
                legacy[previous[2]] = config
                await self.context.settings.set("backups.schedules", legacy)
            await self.repository.save(request.schedule_id, configuration.model_dump())

    async def delete(self, name):
        async with self._settings_lock:
            previous = (await self.configurations()).get(name)
            if previous and previous[1].get("status") == "running":
                from ..error import UserInputError

                raise UserInputError(
                    "Wait for the active schedule run to finish before removing it"
                )
            if previous and previous[2]:
                legacy = self.context.settings.get("backups.schedules", {})
                legacy = {
                    k: v.model_dump() if hasattr(v, "model_dump") else v
                    for k, v in legacy.items()
                    if k != previous[2]
                }
                await self.context.settings.set("backups.schedules", legacy)
            await self.repository.delete(name)

    async def execute(self, name, config, server, slot):
        import time
        from uuid import uuid4

        from ..events.bus import current_correlation_id

        started = time.monotonic()
        failure = None
        run_id = uuid4().hex
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
                await self._execute(config, server, slot)
            except BaseException as error:
                failure = error
                await self.repository.run(
                    name,
                    slot,
                    run_id=run_id,
                    status=(
                        "interrupted"
                        if isinstance(error, asyncio.CancelledError)
                        else "failed"
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
                        owner=(
                            "application"
                            if ":" not in config["task"]
                            else "plugin:" + config["task"].split(":", 1)[0]
                        ),
                    )

    async def _execute(self, config, server, slot):
        if config["task"] == "backup":
            result = await self.context.api.backup_restore.create_server_backup(
                request={
                    "server_name": server.server_name,
                    "purpose": "scheduled",
                    "schedule_slot": slot,
                    **config.get("options", {}),
                }
            )
            if result.status != "success":
                raise RuntimeError("Scheduled backup did not complete")
        elif config["task"] == "verify":
            from datetime import timedelta

            age = config.get("options", {}).get("minimum_age_hours", 168)
            failed = 0
            for item in await server.backups.list_snapshots():
                if server.operation_lock.waiting:
                    raise RuntimeError(
                        "Verification yielded to interactive work; retry later"
                    )
                checked = item.verification.verified_at
                if (
                    item.verification.status != "verified"
                    or not checked
                    or datetime.now(timezone.utc) - datetime.fromisoformat(checked)
                    >= timedelta(hours=age)
                ):
                    try:
                        await server.backups.verify_snapshot(item.backup_id)
                    except Exception:
                        failed += 1
            if failed:
                raise RuntimeError(
                    "Some scheduled archive verifications failed; inspect backup health"
                )
        else:
            if not self.available(config["task"]):
                raise RuntimeError("Scheduled task handler is unavailable")
            handler, owner, _ = self._handlers[config["task"]]
            manager = self.context._plugin_manager
            current = asyncio.current_task()
            tasks = (
                manager.plugin_tasks.setdefault(owner.removeprefix("plugin:"), [])
                if manager
                else []
            )
            if current is not None:
                tasks.append(current)
            try:
                await handler(
                    server_name=server.server_name,
                    options=dict(config.get("options", {})),
                )
            finally:
                if current in tasks:
                    tasks.remove(current)

    async def _maintain_server(self, name):
        try:
            server = self.context.get_server(name, require_installation=False)
            async with self._slots:
                performed = False
                for identifier, (config, state, legacy) in (
                    await self.configurations(name)
                ).items():
                    if not self.available(config["task"]):
                        continue
                    # A host losing one timezone must not block other jobs for the server.
                    from ..utils.timezones import resolve_timezone

                    try:
                        resolve_timezone(config["timezone"])
                    except (ValueError, KeyError):
                        logging.getLogger(__name__).warning(
                            "Scheduled timezone unavailable for '%s'.", identifier
                        )
                        continue

                    async def capture(slot):
                        await self.execute(identifier, config, server, slot)

                    # Keep the legacy signature stable to retain existing activation/history.
                    legacy_config = {
                        k: v
                        for k, v in config.items()
                        if k not in ("task", "server_name", "options")
                    }

                    async def read_state():
                        return await self.repository.state(identifier)

                    async def write_state(value):
                        await self.repository.state(identifier, value)

                    performed = (
                        await run_due(
                            server.backups,
                            config=legacy_config if legacy else config,
                            record_key=(
                                "schedule" if legacy else f"schedule:{identifier}"
                            ),
                            capture=capture,
                            read_state=read_state,
                            write_state=write_state,
                        )
                        or performed
                    )
                if not performed:
                    await server.backups.maintain_backups()
        except Exception:
            logging.getLogger(__name__).warning(
                "Scheduled work needs attention for '%s'.", name, exc_info=True
            )

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
        missing = sum(
            not self.available(config["task"])
            or config["server_name"] not in self.context.state.servers.servers
            for config, state in enabled
        )
        observation = SchedulerDiagnostics(
            running=self.task is not None and not self.task.done(),
            schedules=len(entries),
            enabled=len(enabled),
            active_jobs=len(self._jobs),
            failed=sum(
                state.get("status") in ("failed", "interrupted")
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
                key: value
                for key, value in observation.model_dump().items()
                if key not in ("kind", "last_error_type")
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
            self.task = asyncio.create_task(self._run(), name="scheduler")

    def _finished(self, name, task):
        if self._jobs.get(name) is task:
            self._jobs.pop(name, None)
        self.context.state.runtime.scheduler["active_jobs"] = len(self._jobs)
        if not task.cancelled():
            task.exception()

    async def _run(self):
        import time

        from ..services.lifecycle import LifecyclePhase

        try:
            await self.repository.recover()
            while True:
                if self.context.lifecycle_phase != LifecyclePhase.READY:
                    await asyncio.sleep(1)
                    continue
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
                for name in sorted(names):
                    if name not in self._jobs:
                        task = asyncio.create_task(
                            self._maintain_server(name), name=f"scheduler:{name}"
                        )
                        self._jobs[name] = task
                        task.add_done_callback(
                            lambda done, name=name: self._finished(name, done)
                        )
                self.context.state.runtime.scheduler["active_jobs"] = len(self._jobs)
                await asyncio.sleep(60)
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
        self._handlers.clear()
