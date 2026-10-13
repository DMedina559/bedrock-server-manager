"""Independent bounded database history; domain transactions never await recording."""

import asyncio
import base64
import time
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, delete, func, or_, select

from ..db.models import DiagnosticHistoryRow
from ..error import UserInputError
from .models import (
    DiagnosticHistory,
    DiagnosticOptions,
    DiagnosticRecord,
    DiagnosticRun,
    DiagnosticRuns,
    PersistenceDiagnostics,
)

if TYPE_CHECKING:
    from ..db.database import Database


class HistoryCursor(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    timestamp: float = Field(ge=0)
    id: str = Field(pattern=r"^[0-9a-f]{32}$")


def _decode_cursor(cursor: str) -> HistoryCursor:
    try:
        if len(cursor) > 512:
            raise ValueError("Cursor exceeds size limit")
        return HistoryCursor.model_validate_json(
            base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        )
    except Exception as error:
        raise UserInputError("Invalid diagnostic history cursor") from error


def _encode_cursor(record: DiagnosticRecord) -> str:
    return (
        base64.urlsafe_b64encode(
            HistoryCursor(id=record.id, timestamp=record.timestamp)
            .model_dump_json()
            .encode()
        )
        .decode()
        .rstrip("=")
    )


class DiagnosticHistoryStore:
    def __init__(self, database: "Database", options: DiagnosticOptions):
        self.database = database
        self.options = options
        self.queue: asyncio.Queue[DiagnosticRecord] = asyncio.Queue(options.queue_limit)
        self.dropped = 0
        self.write_failures = 0
        self.accepting = True
        self.last_success_at: float | None = None
        self.last_error_type: str | None = None
        self.read_failures = 0
        self.last_read_success_at: float | None = None
        self.last_read_error_type: str | None = None
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
            except Exception as error:
                self.last_error_type = type(error).__name__
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
                    owner=record.owner,
                    code=record.code,
                    outcome=record.outcome,
                    operation_id=record.operation_id,
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
        self.last_success_at = time.time()
        self.last_error_type = None

    def _read_succeeded(self) -> None:
        self.last_read_success_at = time.time()
        self.last_read_error_type = None

    def _read_failed(self, error: Exception) -> None:
        self.read_failures += 1
        self.last_read_error_type = type(error).__name__

    async def read(
        self,
        *,
        limit: int = 100,
        subsystem: str | None = None,
        instance_id: str | None = None,
        correlation_id: str | None = None,
        owner: str | None = None,
        code: str | None = None,
        outcome: Literal["completed", "failed", "cancelled"] | None = None,
        operation_id: str | None = None,
        cursor: str | None = None,
    ) -> DiagnosticHistory:
        if not 1 <= limit <= 200:
            raise UserInputError("Diagnostic history limit must be between 1 and 200")
        position = _decode_cursor(cursor) if cursor is not None else None
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
                    for column, value in (
                        (DiagnosticHistoryRow.owner, owner),
                        (DiagnosticHistoryRow.code, code),
                        (DiagnosticHistoryRow.outcome, outcome),
                        (DiagnosticHistoryRow.operation_id, operation_id),
                    ):
                        if value is not None:
                            query = query.where(column == value)
                    if position is not None:
                        query = query.where(
                            or_(
                                DiagnosticHistoryRow.timestamp < position.timestamp,
                                (DiagnosticHistoryRow.timestamp == position.timestamp)
                                & (DiagnosticHistoryRow.id < position.id),
                            )
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
                    self._read_succeeded()
                    return DiagnosticHistory(
                        records=records[:limit],
                        available=True,
                        truncated=len(records) > limit,
                        next_cursor=(
                            _encode_cursor(records[limit - 1])
                            if len(records) > limit
                            else None
                        ),
                    )
        except Exception as error:
            self._read_failed(error)
            return DiagnosticHistory(records=[], available=False, truncated=False)

    async def runs(self, *, current_instance: str, limit: int = 20) -> DiagnosticRuns:
        if not 1 <= limit <= 50:
            raise UserInputError("Diagnostic run limit must be between 1 and 50")
        try:
            async with asyncio.timeout(2):
                async with self.database.session_manager() as session:
                    query = (
                        select(
                            DiagnosticHistoryRow.instance_id,
                            func.min(DiagnosticHistoryRow.timestamp).label("first"),
                            func.max(DiagnosticHistoryRow.timestamp).label("last"),
                            func.count().label("total"),
                            func.sum(
                                case(
                                    (DiagnosticHistoryRow.outcome == "failed", 1),
                                    else_=0,
                                )
                            ).label("failed"),
                            func.sum(
                                case(
                                    (DiagnosticHistoryRow.outcome == "cancelled", 1),
                                    else_=0,
                                )
                            ).label("cancelled"),
                        )
                        .where(
                            DiagnosticHistoryRow.timestamp
                            >= time.time() - self.options.retention_days * 86400
                        )
                        .group_by(DiagnosticHistoryRow.instance_id)
                        .order_by(
                            func.max(DiagnosticHistoryRow.timestamp).desc(),
                            DiagnosticHistoryRow.instance_id.desc(),
                        )
                        .limit(limit + 1)
                    )
                    groups = (await session.execute(query)).all()
                    ranked = (
                        select(
                            DiagnosticHistoryRow.id,
                            func.row_number()
                            .over(
                                partition_by=DiagnosticHistoryRow.instance_id,
                                order_by=(
                                    DiagnosticHistoryRow.timestamp.desc(),
                                    DiagnosticHistoryRow.id.desc(),
                                ),
                            )
                            .label("rank"),
                        )
                        .where(
                            DiagnosticHistoryRow.instance_id.in_(
                                [group.instance_id for group in groups[:limit]]
                            )
                        )
                        .subquery()
                    )
                    latest_rows = (
                        (
                            await session.scalars(
                                select(DiagnosticHistoryRow)
                                .join(ranked, ranked.c.id == DiagnosticHistoryRow.id)
                                .where(ranked.c.rank == 1)
                            )
                        ).all()
                        if groups
                        else []
                    )
                    latest_by_instance = {row.instance_id: row for row in latest_rows}
                    runs = []
                    for group in groups[:limit]:
                        latest = latest_by_instance[group.instance_id]
                        record = DiagnosticRecord.model_validate(latest.record)
                        runs.append(
                            DiagnosticRun(
                                instance_id=group.instance_id,
                                first_record_at=group.first,
                                last_record_at=group.last,
                                retained_records=group.total,
                                failed_records=group.failed,
                                cancelled_records=group.cancelled,
                                current_instance=group.instance_id == current_instance,
                                last_observed_phase=record.phase,
                                backend_version=record.backend_version,
                                recording_closed=(
                                    True
                                    if record.operation == "diagnostics_closed"
                                    else None
                                ),
                            )
                        )
                    self._read_succeeded()
                    return DiagnosticRuns(
                        runs=runs, available=True, truncated=len(groups) > limit
                    )
        except Exception as error:
            self._read_failed(error)
            return DiagnosticRuns(runs=[], available=False, truncated=False)

    def snapshot(self) -> PersistenceDiagnostics:
        return PersistenceDiagnostics(
            writer_status=(
                "closed"
                if not self.accepting
                else (
                    "not_started"
                    if self._worker is None
                    else "failed" if self._worker.done() else "running"
                )
            ),
            last_success_at=self.last_success_at,
            last_error_type=self.last_error_type,
            read_failures=self.read_failures,
            last_read_success_at=self.last_read_success_at,
            last_read_error_type=self.last_read_error_type,
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
