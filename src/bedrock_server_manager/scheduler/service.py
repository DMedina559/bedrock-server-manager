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

    @property
    def repository(self):
        from ..db.repositories.scheduler import SchedulerRepository

        return SchedulerRepository(self.context.db)

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
            future = [
                slot
                for slot in occurrences(
                    config, config["server_name"], datetime.now(timezone.utc)
                )
                if slot > datetime.now(timezone.utc)
            ]
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
        return ListSchedulesResponse(schedules=entries, task_types=sorted(types))

    async def save(self, request):
        from ..error import UserInputError

        self.context.get_server(
            request.configuration.server_name, require_installation=False
        )
        task = request.configuration.task
        options = request.configuration.options
        allowed = {
            "backup": {"encrypted", "include_packs"},
            "verify": {"minimum_age_hours"},
        }.get(task)
        if allowed is not None and set(options) - allowed:
            raise UserInputError("Unknown scheduled task option")
        if task == "backup" and any(type(v) is not bool for v in options.values()):
            raise UserInputError("Backup options must be booleans")
        if task == "verify" and (
            type(options.get("minimum_age_hours", 168)) is not int
            or not 0 <= options.get("minimum_age_hours", 168) <= 8760
        ):
            raise UserInputError("Verification age must be an integer from 0 to 8760")
        async with self._settings_lock:
            rows = await self.configurations()
            previous = rows.get(request.schedule_id)
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
                config = request.configuration.model_dump(
                    exclude={"task", "server_name", "options"}
                )
                legacy = self.context.settings.get("backups.schedules", {})
                legacy = {
                    k: v.model_dump() if hasattr(v, "model_dump") else v
                    for k, v in legacy.items()
                }
                legacy[previous[2]] = config
                await self.context.settings.set("backups.schedules", legacy)
            await self.repository.save(
                request.schedule_id, request.configuration.model_dump()
            )

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
        from uuid import uuid4

        from ..events.bus import current_correlation_id

        run_id = uuid4().hex
        with self.context.events.operations.scope(
            "scheduler.run", server_name=server.server_name
        ):
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
        from ..diagnostics.models import PluginValues

        snapshot = await self.snapshot()
        entries = snapshot.schedules
        failed = sum(e.last_status in ("failed", "interrupted") for e in entries)
        unavailable = sum(not e.available for e in entries)
        return PluginValues(
            health="degraded" if failed or unavailable else "ok",
            values={
                "schedules": len(entries),
                "enabled": sum(e.configuration.enabled for e in entries),
                "running": sum(e.last_status == "running" for e in entries),
                "failed": failed,
                "unavailable": unavailable,
            },
        )

    def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run(), name="scheduler")

    def _finished(self, name, task):
        if self._jobs.get(name) is task:
            self._jobs.pop(name, None)
        if not task.cancelled():
            task.exception()

    async def _run(self):
        from ..services.lifecycle import LifecyclePhase

        try:
            await self.repository.recover()
            while True:
                if self.context.lifecycle_phase != LifecyclePhase.READY:
                    await asyncio.sleep(1)
                    continue
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
                await asyncio.sleep(60)
        finally:
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
