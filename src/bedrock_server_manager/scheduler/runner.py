"""Database-owned execution cursors, claims, and bounded retry decisions.

External effects are at-least-once across a crash. Handlers opting into execution
context can use the stable slot as their idempotency key.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .engine import occurrences, signature


class DeferredRun(Exception):
    """Contention postpones work without consuming its retry budget."""


def activation(config, moment=None):
    return {
        "configuration": signature(config),
        "activated_at": (moment or datetime.now(timezone.utc)).isoformat(),
        "status": "waiting" if config["enabled"] else "disabled",
        "attempts": 0,
    }


def candidate(config, record, moment, name=""):
    """Choose a pending retry, explicit request, or latest eligible occurrence."""
    if record.get("lease"):
        return None
    if record.get("requested_slot"):
        return record["requested_slot"], moment, True
    pending = record.get("status") in ("failed", "interrupted", "deferred")
    if pending and record.get("slot") and record.get("occurrence_at"):
        occurrence = datetime.fromisoformat(record["occurrence_at"])
        retry = record.get("next_retry_at")
        if (
            record.get("blocked_reason") != "retry_expired"
            and record.get("attempts", 0) < 3
            and moment - occurrence < timedelta(days=1)
        ):
            if retry and moment < datetime.fromisoformat(retry):
                return None
            return record["slot"], occurrence, bool(record.get("manual"))
    if not config["enabled"]:
        return None
    activated = datetime.fromisoformat(record["activated_at"])
    due = [
        s
        for s in occurrences(config, config["server_name"], moment)
        if activated <= s <= moment
    ]
    if not due:
        return None
    occurrence = due[-1]
    slot = "schedule:" + name + ":" + signature(config) + ":" + occurrence.isoformat()
    if slot in record.get("completed_slots", []):
        return None
    if record.get("slot") == slot and (
        record.get("attempts", 0) >= 3
        or record.get("blocked_reason") == "retry_expired"
        or (pending and moment - occurrence >= timedelta(days=1))
    ):
        return None
    return slot, occurrence, False


async def run_schedule(
    repository,
    name,
    config,
    server,
    execute,
    *,
    reconcile=None,
    moment=None,
    check_contention=True,
):
    """Claim against the latest definition before invoking any external effect."""
    now = moment or datetime.now(timezone.utc)
    lease = uuid4().hex

    def claim(current, record):
        if signature(current) != signature(config):
            return None
        if record.get("configuration") != signature(config):
            # Upgrade legacy identities without replaying a completed occurrence.
            old_sig = record.get("configuration")
            old_slot = record.get("slot")
            if old_slot and old_sig and old_sig + ":" in old_slot:
                stamp = old_slot.split(old_sig + ":", 1)[1]
                try:
                    datetime.fromisoformat(stamp)
                except ValueError:
                    pass
                else:
                    record["slot"] = (
                        "schedule:" + name + ":" + signature(config) + ":" + stamp
                    )
                    record.setdefault("occurrence_at", stamp)
                    if record.get("status") in ("completed", "skipped"):
                        record["completed_slots"] = [record["slot"]]
            record["configuration"] = signature(config)
            record.setdefault("activated_at", now.isoformat())
            record.setdefault("status", "waiting")
        choice = candidate(config, record, now, name)
        record["last_evaluated_at"] = now.isoformat()
        if choice is None:
            if (
                not record.get("lease")
                and record.get("status") in ("failed", "interrupted", "deferred")
                and record.get("occurrence_at")
                and now - datetime.fromisoformat(record["occurrence_at"])
                >= timedelta(days=1)
            ):
                record.update(
                    status="failed",
                    blocked_reason="retry_expired",
                    next_retry_at=None,
                    error="Automatic retry window expired; review before retrying.",
                )
            return None
        slot, occurrence, manual = choice
        same = record.get("slot") == slot
        if (
            not manual
            and not (same and (record.get("begun") or record.get("attempts", 0) > 0))
            and not config["catch_up"]
            and (now - occurrence).total_seconds() > 120
        ):
            record.update(
                slot=slot,
                status="skipped",
                blocked_reason="missed_occurrence",
                error=None,
                attempts=0,
                next_retry_at=None,
            )
            record["completed_slots"] = (record.get("completed_slots", []) + [slot])[
                -32:
            ]
            return None
        # Claiming is short and transactional. Long work never holds a DB lock.
        if check_contention and (
            server.operation_lock.locked() or server.operation_lock.waiting
        ):
            record.update(
                slot=slot,
                occurrence_at=occurrence.isoformat(),
                manual=manual,
                status="deferred",
                blocked_reason="server_busy",
                begun=record.get("begun", False) if same else False,
                attempts=record.get("attempts", 0) if same else 0,
            )
            return None
        attempts = record.get("attempts", 0) if same else 0
        record.update(
            slot=slot,
            occurrence_at=occurrence.isoformat(),
            manual=manual,
            attempts=attempts + 1,
            begun=True,
            lease=lease,
            status="running",
            next_retry_at=None,
            blocked_reason=None,
            error=None,
        )
        record.pop("requested_slot", None)
        return dict(record)

    claimed = await repository.mutate(name, claim)
    if claimed is None:
        return False
    slot = claimed["slot"]
    outcome = "completed"
    error = None
    cancelled = None
    try:
        recovered = await repository.completed(name, slot)
        if not recovered and reconcile is not None:
            recovered = await reconcile(slot)
            if recovered:
                await repository.run(name, slot, run_id=uuid4().hex, status="completed")
        if not recovered:
            await execute(slot, claimed)
    except DeferredRun:
        outcome = "deferred"
    except asyncio.CancelledError as exc:
        outcome, error, cancelled = "interrupted", "Task interrupted by shutdown.", exc
    except Exception:
        outcome, error = (
            "failed",
            "Scheduled task failed; inspect diagnostics and logs.",
        )

    finished = now if moment is not None else datetime.now(timezone.utc)

    def finish(current, record):
        if record.get("lease") != lease:
            return
        record.pop("lease", None)
        # An edit/pause made during this run owns its new cursor.
        if signature(current) != signature(config):
            return
        record.update(status=outcome, error=error)
        if outcome == "completed":
            record.update(
                last_success_at=finished.isoformat(),
                next_retry_at=None,
            )
            record["completed_slots"] = (record.get("completed_slots", []) + [slot])[
                -32:
            ]
        elif outcome == "deferred":
            record.update(
                attempts=max(0, record["attempts"] - 1),
                blocked_reason="interactive_work",
            )
        else:
            record["next_retry_at"] = (
                (finished + timedelta(seconds=60 * 2 ** record["attempts"])).isoformat()
                if record["attempts"] < 3
                else None
            )
            record["blocked_reason"] = (
                "retry_exhausted" if record["attempts"] >= 3 else None
            )
            if record["next_retry_at"] and datetime.fromisoformat(
                record["next_retry_at"]
            ) - datetime.fromisoformat(record["occurrence_at"]) >= timedelta(days=1):
                record.update(next_retry_at=None, blocked_reason="retry_expired")

    await repository.mutate(name, finish)
    if cancelled is not None:
        raise cancelled
    return True


def next_attempt(config, record, moment, name):
    """Forecast pending work separately from the next calendar occurrence."""
    if record.get("lease"):
        return None
    try:
        retry = record.get("next_retry_at")
        if retry and config["enabled"] and record.get("attempts", 0) < 3:
            occurrence = datetime.fromisoformat(record["occurrence_at"])
            if moment - occurrence < timedelta(days=1):
                return retry
        choice = candidate(config, record, moment, name)
        if choice is None:
            return None
        _, occurrence, manual = choice
        begun = choice[0] == record.get("slot") and (
            record.get("begun") or record.get("attempts", 0) > 0
        )
        if (
            manual
            or begun
            or config["catch_up"]
            or (moment - occurrence).total_seconds() <= 120
        ):
            return moment.isoformat()
    except (ValueError, KeyError):
        return None
    return None
