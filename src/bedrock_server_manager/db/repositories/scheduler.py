"""Transactional scheduler definitions, cursors, and bounded attempt history."""

from sqlalchemy import delete, select

from ..models import Schedule, ScheduleRun


class SchedulerRepository:
    def __init__(self, db):
        self.db = db

    async def list(self):
        async with self.db.session_manager() as session:
            rows = (
                (await session.execute(select(Schedule).order_by(Schedule.schedule_id)))
                .scalars()
                .all()
            )
            return [
                (r.schedule_id, dict(r.configuration), dict(r.state), r.legacy_server)
                for r in rows
            ]

    async def save(self, name, config, *, legacy_server=None, initial_state=None):
        async with self.db.session_manager() as session:
            row = await session.get(Schedule, name)
            if row is None:
                session.add(
                    Schedule(
                        schedule_id=name,
                        configuration=config,
                        state=initial_state or {},
                        legacy_server=legacy_server,
                    )
                )
            elif row.configuration != config:
                row.configuration = config
                # Engine detects configuration changes and activates at its next poll.
            await session.commit()

    async def delete(self, name):
        async with self.db.session_manager() as session:
            await session.execute(delete(Schedule).where(Schedule.schedule_id == name))
            await session.execute(
                delete(ScheduleRun).where(ScheduleRun.schedule_id == name)
            )
            await session.commit()

    async def state(self, name, value=None):
        async with self.db.session_manager() as session:
            row = await session.get(Schedule, name)
            if row is None:
                raise RuntimeError("Schedule was removed")
            if value is None:
                return dict(row.state)
            row.state = dict(value)
            await session.commit()

    async def run(self, name, slot, *, run_id, status, correlation_id=None, error=None):
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).isoformat()
        async with self.db.session_manager() as session:
            row = await session.get(ScheduleRun, run_id)
            if row is None:
                row = ScheduleRun(
                    run_id=run_id,
                    schedule_id=name,
                    slot=slot,
                    started_at=stamp,
                    status=status,
                    correlation_id=correlation_id,
                )
                session.add(row)
            row.status = status
            row.error = error
            if status != "running":
                row.finished_at = stamp
            # Include the newly inserted attempt even with autoflush disabled.
            await session.flush()
            # Retain the latest 100 attempts per schedule.
            stale = (
                (
                    await session.execute(
                        select(ScheduleRun.run_id)
                        .where(ScheduleRun.schedule_id == name)
                        .order_by(
                            ScheduleRun.started_at.desc(), ScheduleRun.run_id.desc()
                        )
                        .offset(100)
                    )
                )
                .scalars()
                .all()
            )
            if stale:
                await session.execute(
                    delete(ScheduleRun).where(ScheduleRun.run_id.in_(stale))
                )
            await session.commit()

    async def history(self, name, limit=20):
        async with self.db.session_manager() as session:
            rows = (
                (
                    await session.execute(
                        select(ScheduleRun)
                        .where(ScheduleRun.schedule_id == name)
                        .order_by(ScheduleRun.started_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return [
                {
                    k: getattr(r, k)
                    for k in (
                        "run_id",
                        "schedule_id",
                        "slot",
                        "status",
                        "started_at",
                        "finished_at",
                        "correlation_id",
                        "error",
                    )
                }
                for r in rows
            ]

    async def recover(self):
        """Record interrupted attempts once on application startup."""
        async with self.db.session_manager() as session:
            rows = (
                (
                    await session.execute(
                        select(ScheduleRun).where(ScheduleRun.status == "running")
                    )
                )
                .scalars()
                .all()
            )
            from datetime import datetime, timezone

            for row in rows:
                row.status = "interrupted"
                row.finished_at = datetime.now(timezone.utc).isoformat()
                row.error = "Application stopped before the task completed."
            schedules = (await session.execute(select(Schedule))).scalars().all()
            for row in schedules:
                if row.state.get("status") == "running":
                    row.state = dict(
                        row.state,
                        status="interrupted",
                        error="Application stopped before the task completed.",
                    )
            await session.commit()
