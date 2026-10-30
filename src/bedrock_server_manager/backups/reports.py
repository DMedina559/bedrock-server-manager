"""Explicitly allowlisted recovery evidence; never export paths, keys or values."""

import asyncio
import hashlib
from datetime import datetime

from ..utils.threads import run_in_thread
from .catalog import now
from .models import (
    RecoveryReport,
    RecoveryReportArchive,
    RecoveryReportDrill,
    RecoveryReportOutcome,
    RecoveryReportReview,
)
from .recovery import RestoreJournal


def reference(identifier):
    return hashlib.sha256(identifier.encode()).hexdigest()


def timestamp(value):
    try:
        return datetime.fromisoformat(value).isoformat() if value else None
    except (ValueError, TypeError):
        return None


def record_review(backups, plan):
    # Values and file names from comparisons are intentionally excluded.
    review = RecoveryReportReview(
        recorded_at=now(),
        archive_reference=reference(plan.backup_id),
        components=plan.components,
        dry_run=plan.dry_run,
        checked_files=plan.checked_files,
        change_counts=plan.change_counts,
        sufficient_space=plan.sufficient_space,
        volumes=plan.volumes,
    )
    value = backups.catalog.load()
    value["last_review"] = review.model_dump(mode="json")
    backups.catalog.save(value)


async def record_outcome(backups, identifier, components, result=None, error=None):
    outcome = RecoveryReportOutcome(
        recorded_at=now(),
        archive_reference=reference(identifier),
        components=components,
        status=(
            "completed"
            if result is not None
            else "cancelled" if isinstance(error, asyncio.CancelledError) else "failed"
        ),
        committed=result.committed if result is not None else None,
        restarted=result.restarted if result is not None else False,
        restart_failed=bool(result.restart_error) if result is not None else False,
        cleanup_needed=(
            bool(result.cleanup_warning)
            if result is not None
            else RestoreJournal(backups.server).path.exists()
        ),
    )

    def save():
        value = backups.catalog.load()
        value["last_restore"] = outcome.model_dump(mode="json")
        backups.catalog.save(value)

    try:
        await run_in_thread(save)
    except (Exception, asyncio.CancelledError):
        # Reporting must not turn a committed restore into an apparent failure.
        backups.logger.warning("Recovery report outcome could not be updated.")


async def recovery_report(backups):
    summaries = await backups.list_snapshots()
    health = await backups.backup_health()
    value = await run_in_thread(backups.catalog.load)
    archives = [
        RecoveryReportArchive(
            archive_reference=reference(item.backup_id),
            encrypted=item.encrypted,
            key_available=not item.encrypted
            or item.key_id not in health.missing_key_ids,
            verification_status=("failed" if item.error else item.verification.status),
            verified_at=timestamp(item.verification.verified_at),
            copies_completed=sum(
                copy.status == "completed" for copy in item.copies.values()
            ),
            copies_failed=sum(copy.status == "failed" for copy in item.copies.values()),
        )
        for item in summaries[:100]
    ]
    drill = health.drill
    return RecoveryReport(
        generated_at=now(),
        readiness=health.readiness,
        archive_count=health.count,
        archives_omitted=max(0, len(summaries) - len(archives)),
        missing_key_count=len(health.missing_key_ids),
        destination_failures=health.destination_failures,
        recovery_pending=RestoreJournal(backups.server).path.exists(),
        archives=archives,
        last_review=(
            RecoveryReportReview.model_validate(value["last_review"])
            if value.get("last_review")
            else None
        ),
        last_restore=(
            RecoveryReportOutcome.model_validate(value["last_restore"])
            if value.get("last_restore")
            else None
        ),
        last_drill=(
            RecoveryReportDrill(
                archive_reference=reference(drill["backup_id"]),
                status=drill["status"],
                checked_at=timestamp(drill.get("checked_at")),
                checked_files=drill.get("checked_files", 0),
            )
            if drill
            else None
        ),
    )
