"""Lifecycle-owned backup verification and destination retries."""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import AppContext


class BackupMaintenance:
    def __init__(self, context: "AppContext"):
        self.context = context
        self.task: asyncio.Task | None = None
        self._jobs: dict[str, asyncio.Task] = {}
        self._schedule_slots = asyncio.Semaphore(4)
        self._maintenance_slots = asyncio.Semaphore(2)

    def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run(), name="backup-maintenance")

    async def _maintain_server(self, name):
        from .schedule import run_due

        try:
            server = self.context.get_server(name, require_installation=False)

            async def capture(slot):
                await self.context.api.backup_restore.create_server_backup(
                    request={
                        "server_name": name,
                        "purpose": "scheduled",
                        "schedule_slot": slot,
                    }
                )

            async with self._schedule_slots:
                if server.operation_lock.locked() or server.operation_lock.waiting:
                    return
                captured = await run_due(server.backups, capture=capture)
            if not captured:
                async with self._maintenance_slots:
                    await server.backups.maintain_backups()
        except Exception:
            logging.getLogger(__name__).warning(
                "Backup maintenance needs attention for '%s'.", name
            )

    def _finished(self, name, task):
        if self._jobs.get(name) is task:
            self._jobs.pop(name, None)
        if not task.cancelled():
            task.exception()

    async def _run(self):
        from ..services.lifecycle import LifecyclePhase

        try:
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
                            self._maintain_server(name),
                            name=f"backup-maintenance:{name}",
                        )
                        self._jobs[name] = task
                        task.add_done_callback(
                            lambda finished, name=name: self._finished(name, finished)
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
