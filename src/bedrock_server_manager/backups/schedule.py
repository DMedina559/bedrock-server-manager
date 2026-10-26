"""Durable daily schedules with timezone, catch-up, staggering, and retry limits."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..utils.threads import run_in_thread


def config_for(backups):
    raw = backups.server.settings.get("backups.schedules", {}).get(
        backups.server.server_name
    )
    return raw.model_dump() if hasattr(raw, "model_dump") else raw


def signature(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def occurrences(config, name, moment):
    zone = ZoneInfo(config["timezone"])
    local = moment.astimezone(zone)
    hour, minute = map(int, config["time"].split(":"))
    offset = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % (
        config["stagger_minutes"] + 1
    )
    slots = []
    for delta in range(-8, 9):
        date = (local + timedelta(days=delta)).date()
        if date.weekday() not in config["weekdays"]:
            continue
        # On a repeated hour, use the first occurrence. A missing hour shifts forward.
        wall = datetime(
            date.year, date.month, date.day, hour, minute, tzinfo=zone, fold=0
        )
        slots.append(wall.astimezone(timezone.utc) + timedelta(minutes=offset))
    return sorted(slots)


def status(backups, value, moment=None):
    config = config_for(backups)
    if not config:
        return None
    moment = moment or datetime.now(timezone.utc)
    record = value.get("schedule", {})
    future = [
        slot
        for slot in occurrences(config, backups.server.server_name, moment)
        if slot > moment
    ]
    return {
        "enabled": config["enabled"],
        "timezone": config["timezone"],
        "time": config["time"],
        "next_run_at": future[0].isoformat() if future and config["enabled"] else None,
        "last_status": record.get("status"),
        "last_success_at": record.get("last_success_at"),
        "last_error": record.get("error"),
        "attempts": record.get("attempts", 0),
    }


async def run_due(backups, moment=None, *, capture=None):
    """At most one scheduled capture; restart recovery coalesces missed slots."""
    config = config_for(backups)
    if not config or (
        backups.server.operation_lock.locked() or backups.server.operation_lock.waiting
    ):
        return False
    moment = moment or datetime.now(timezone.utc)
    async with backups.server.operation_lock:
        value = await run_in_thread(backups.catalog.load)
        record = value.get("schedule", {})
        sig = signature(config)
        if not config["enabled"]:
            if (
                record.get("configuration") == sig
                and record.get("status") == "disabled"
            ):
                return False
            value["schedule"] = {
                "configuration": sig,
                "activated_at": moment.isoformat(),
                "status": "disabled",
            }
            await run_in_thread(backups.catalog.save, value)
            return False
        if record.get("configuration") != sig:
            value["schedule"] = {
                "configuration": sig,
                "activated_at": moment.isoformat(),
                "status": "waiting",
            }
            await run_in_thread(backups.catalog.save, value)
            return False
        activated = datetime.fromisoformat(record["activated_at"])
        due = [
            slot
            for slot in occurrences(config, backups.server.server_name, moment)
            if activated <= slot <= moment
        ]
        if not due:
            return False
        slot = due[-1]
        identifier = sig + ":" + slot.isoformat()
        if record.get("slot") == identifier and record.get("status") in (
            "completed",
            "skipped",
        ):
            return False
        if not config["catch_up"] and (moment - slot).total_seconds() > 120:
            record.update(
                slot=identifier, status="skipped", error="Missed run skipped by policy."
            )
            value["schedule"] = record
            await run_in_thread(backups.catalog.save, value)
            return False
        if record.get("slot") != identifier:
            record.update(slot=identifier, attempts=0, next_retry_at=None)
        if record.get("attempts", 0) >= 3 and record.get("status") != "running":
            return False
        if record.get("next_retry_at") and moment < datetime.fromisoformat(
            record["next_retry_at"]
        ):
            return False
        # Creation records its intended filename/slot before publishing the archive.
        # A crash after publication must not generate a duplicate on restart.
        existing = next(
            (
                name
                for name, item in value["archives"].items()
                if item.get("schedule_slot") == identifier
                and (backups.catalog.directory / name).is_file()
            ),
            None,
        )
        record.update(
            status="running", attempts=record.get("attempts", 0) + 1, error=None
        )
        value["schedule"] = record
        await run_in_thread(backups.catalog.save, value)
        try:
            if existing:
                await backups.verify_snapshot(existing)
            elif capture is not None:
                await capture(identifier)
            else:
                await backups.create_snapshot(
                    purpose="scheduled", _schedule_slot=identifier
                )
            record.update(
                status="completed",
                last_success_at=moment.isoformat(),
                next_retry_at=None,
            )
        except Exception:
            record.update(
                status="failed",
                error="Scheduled backup failed; inspect backup health and logs.",
                next_retry_at=(
                    moment + timedelta(seconds=min(3600, 60 * 2 ** record["attempts"]))
                ).isoformat(),
            )
            backups.logger.warning(
                "Scheduled backup needs attention for '%s'.", backups.server.server_name
            )
        latest = await run_in_thread(backups.catalog.load)
        latest["schedule"] = record
        await run_in_thread(backups.catalog.save, latest)
        return True
