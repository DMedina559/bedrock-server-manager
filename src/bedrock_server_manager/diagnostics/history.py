"""Independent bounded database history; domain transactions never await recording."""

import asyncio
import time
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from ..db.models import DiagnosticHistoryRow
from .models import (
    DiagnosticHistory,
    DiagnosticOptions,
    DiagnosticRecord,
    PersistenceDiagnostics,
)

if TYPE_CHECKING:
    from ..db.database import Database


class DiagnosticHistoryStore:
    def __init__(self, database: "Database", options: DiagnosticOptions):
        self.database = database
        self.options = options
        self.queue: asyncio.Queue[DiagnosticRecord] = asyncio.Queue(options.queue_limit)
        self.dropped = 0
        self.write_failures = 0
        self.accepting = True
        self._worker: asyncio.Task | None = None

    def start(self) -> None:
        if self._worker is None and self.accepting:
            self._worker = asyncio.create_task(self._run(), name="diagnostics-history")

    def enqueue(self, record: DiagnosticRecord) -> None:
        if not self.accepting:
            self.dropped += 1
            return
        try:
            self.queue.put_nowait(record.model_copy(deep=True))
        except asyncio.QueueFull:
            self.dropped += 1

    async def _run(self) -> None:
        while True:
            record = await self.queue.get()
            try:
                async with asyncio.timeout(2):
                    await self._write(record)
            except asyncio.CancelledError:
                self.dropped += 1
                raise
            except Exception:
                self.write_failures += 1
                self.dropped += 1
            finally:
                self.queue.task_done()

    async def _write(self, record: DiagnosticRecord) -> None:
        async with self.database.session_manager() as session:
            session.add(
                DiagnosticHistoryRow(
                    id=record.id,
                    instance_id=record.instance_id,
                    timestamp=record.timestamp,
                    subsystem=record.subsystem,
                    correlation_id=record.correlation_id,
                    record=record.model_dump(mode="json"),
                )
            )
            await session.flush()
            await session.execute(
                delete(DiagnosticHistoryRow).where(
                    DiagnosticHistoryRow.timestamp
                    < time.time() - self.options.retention_days * 86400
                )
            )
            overflow = (
                select(DiagnosticHistoryRow.id)
                .order_by(
                    DiagnosticHistoryRow.timestamp.desc(),
                    DiagnosticHistoryRow.id.desc(),
                )
                .offset(self.options.history_limit)
                .limit(self.options.queue_limit + 1)
            )
            ids = (await session.scalars(overflow)).all()
            if ids:
                await session.execute(
                    delete(DiagnosticHistoryRow).where(DiagnosticHistoryRow.id.in_(ids))
                )
            await session.commit()

    async def read(
        self,
        *,
        limit: int = 100,
        subsystem: str | None = None,
        instance_id: str | None = None,
        correlation_id: str | None = None,
    ) -> DiagnosticHistory:
        try:
            async with asyncio.timeout(2):
                async with self.database.session_manager() as session:
                    query = select(DiagnosticHistoryRow).where(
                        DiagnosticHistoryRow.timestamp
                        >= time.time() - self.options.retention_days * 86400
                    )
                    if subsystem is not None:
                        query = query.where(DiagnosticHistoryRow.subsystem == subsystem)
                    if instance_id is not None:
                        query = query.where(
                            DiagnosticHistoryRow.instance_id == instance_id
                        )
                    if correlation_id is not None:
                        query = query.where(
                            DiagnosticHistoryRow.correlation_id == correlation_id
                        )
                    rows = (
                        await session.scalars(
                            query.order_by(
                                DiagnosticHistoryRow.timestamp.desc(),
                                DiagnosticHistoryRow.id.desc(),
                            ).limit(limit + 1)
                        )
                    ).all()
                    records = [
                        DiagnosticRecord.model_validate(row.record) for row in rows
                    ]
                    return DiagnosticHistory(
                        records=records[:limit],
                        available=True,
                        truncated=len(records) > limit,
                    )
        except Exception:
            return DiagnosticHistory(records=[], available=False, truncated=False)

    def snapshot(self) -> PersistenceDiagnostics:
        return PersistenceDiagnostics(
            queued=self.queue.qsize(),
            queue_limit=self.options.queue_limit,
            dropped=self.dropped,
            write_failures=self.write_failures,
            accepting=self.accepting,
            history_limit=self.options.history_limit,
            retention_days=self.options.retention_days,
        )

    async def close(self) -> None:
        if not self.accepting:
            return
        if self._worker is None and not self.queue.empty():
            self.start()
        self.accepting = False
        if self._worker is None:
            self.dropped += self.queue.qsize()
            return
        try:
            async with asyncio.timeout(3):
                await self.queue.join()
        except TimeoutError:
            self.dropped += self.queue.qsize()
        finally:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
            while not self.queue.empty():
                self.queue.get_nowait()
                self.queue.task_done()
