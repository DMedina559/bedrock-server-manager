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
        while True:
            for name in list(self.context.state.servers.servers):
                try:
                    server = self.context.get_server(name, require_installation=False)
                    # Do not queue maintenance behind an interactive operation.
                    if server.operation_lock.locked():
                        continue
                    await server.backups.maintain_backups()
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Backup maintenance needs attention for '%s'.", name
                    )
            await asyncio.sleep(3600)

    async def shutdown(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
