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

    def start(self):
        if self.task is None:
            self.task = asyncio.create_task(self._run(), name="backup-maintenance")

    async def _run(self):
        from ..services.lifecycle import LifecyclePhase

        while True:
            if self.context.lifecycle_phase != LifecyclePhase.READY:
                await asyncio.sleep(1)
                continue
            for name in list(self.context.state.servers.servers):
                try:
                    server = self.context.get_server(name, require_installation=False)
                    # Do not queue maintenance behind an interactive operation.
                    if server.operation_lock.locked() or server.operation_lock.waiting:
                        continue
                    from .schedule import run_due

                    async def capture(slot, server_name=name):
                        await self.context.api.backup_restore.create_server_backup(
                            request={
                                "server_name": server_name,
                                "purpose": "scheduled",
                                "schedule_slot": slot,
                            }
                        )

                    if not await run_due(server.backups, capture=capture):
                        await server.backups.maintain_backups()
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Backup maintenance needs attention for '%s'.", name
                    )
            await asyncio.sleep(60)

    async def shutdown(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
