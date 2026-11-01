"""Durable daily schedules with timezone, catch-up, staggering, and retry limits."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from ..utils.timezones import resolve_timezone


def signature(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def occurrences(config, name, moment):
    zone = resolve_timezone(config["timezone"])
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


def status(backups, value=None, moment=None):
    state = getattr(backups.server, "state", None)
    records = getattr(getattr(state, "scheduler", None), "records", {}) or {}
    matching = [
        (config, record)
        for config, record, _ in records.values()
        if config.get("server_name") == backups.server.server_name
        and config.get("task") in ("backup:create", "backup")
    ]
    if not matching:
        return None
    # Prefer an enabled schedule if multiple exist.
    matching.sort(key=lambda item: not item[0].get("enabled", False))
    config, record = matching[0]
    moment = moment or datetime.now(timezone.utc)
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
