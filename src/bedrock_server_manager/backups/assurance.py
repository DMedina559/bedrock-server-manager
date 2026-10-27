"""Recovery readiness, isolated drills, durable alerts and reviewed external cleanup."""

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..error import BackupRestoreError
from ..utils.threads import run_in_thread
from .archive import digest, safe_name
from .models import DestinationCleanupPlan


def utcnow():
    return datetime.now(timezone.utc)


def parsed_time(value):
    stamp = datetime.fromisoformat(value)
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=timezone.utc)


def destination_root(backups, name):
    config = backups.destination_configs().get(name)
    if not config or not config.get("enabled", True):
        raise BackupRestoreError("Destination is not enabled.")
    base = Path(config["path"])
    safe_name(backups.server.server_name)
    root = base / backups.server.server_name
    if (
        not base.is_absolute()
        or not base.is_dir()
        or base.is_symlink()
        or root.is_symlink()
    ):
        raise BackupRestoreError("Destination is unavailable or unsafe.")
    if root.resolve() == Path(backups._directory()).resolve():
        raise BackupRestoreError("Destination must differ from local storage.")
    return config, root


def location_id(config):
    return hashlib.sha256(str(Path(config["path"]).resolve()).encode()).hexdigest()


def remember_copy(backups, identifier, name, source):
    config, root = destination_root(backups, name)
    value = backups.catalog.load()
    record = value["archives"].get(identifier, {})
    index = value.setdefault("destinations", {}).setdefault(name, {})
    if index.get("location") != location_id(config):
        index.clear()
        index.update(location=location_id(config), archives={})
    index["archives"][identifier] = {
        "sha256": digest(root / source.name),
        "size": source.stat().st_size,
        "created_at": record.get("created_at", utcnow().isoformat()),
        "pinned": record.get("pinned", False),
        "protected_until": record.get("protected_until"),
    }
    if identifier in index.get("pending_delete", []):
        index["pending_delete"].remove(identifier)
    backups.catalog.save(value)


def destination_health(backups):
    result = {}
    for name, config in backups.destination_configs().items():
        if not config.get("enabled", True):
            result[name] = {"enabled": False}
            continue
        try:
            _, root = destination_root(backups, name)
            available = shutil.disk_usage(root if root.is_dir() else root.parent).free
            result[name] = {
                "enabled": True,
                "available": True,
                "available_bytes": available,
                "low_space": available < config.get("min_free_bytes", 1073741824),
            }
        except (OSError, BackupRestoreError):
            result[name] = {"enabled": True, "available": False, "low_space": False}
    return result


def copy_current(backups, identifier, name, config, value):
    index = value.get("destinations", {}).get(name, {})
    if index.get("location") != location_id(config):
        return False
    record = index.get("archives", {}).get(identifier)
    if record is None:
        return False
    try:
        _, root = destination_root(backups, name)
        path = root / safe_name(identifier)
        return (
            path.is_file()
            and not path.is_symlink()
            and path.stat().st_size == record["size"]
        )
    except (OSError, BackupRestoreError):
        return False


def readiness(backups, summaries, value, known):
    moment = utcnow()
    age = timedelta(
        hours=backups.server.settings.get("backups.readiness_max_age_hours", 48)
    )
    usable = [
        item
        for item in summaries
        if item.error is None
        and item.verification.status == "verified"
        and (not item.encrypted or item.key_id in known)
    ]
    usable.sort(key=lambda item: item.created_at or "", reverse=True)
    best = usable[0] if usable else None
    reasons = []
    if best is None:
        reasons.append("No verified backup with an available recovery key.")
    elif not best.created_at or moment - parsed_time(best.created_at) > age:
        reasons.append("The latest usable backup is older than the readiness limit.")
    if any(item.error or item.verification.status == "failed" for item in summaries):
        reasons.append("Some archives failed verification.")
    if any(item.encrypted and item.key_id not in known for item in summaries):
        reasons.append("Some archives need missing recovery keys.")
    destinations = destination_health(backups)
    for name, item in destinations.items():
        item["cleanup_pending"] = len(
            value.get("destinations", {}).get(name, {}).get("pending_delete", [])
        )
    if any(item.get("cleanup_pending") for item in destinations.values()):
        reasons.append(
            "External cleanup was interrupted. Review a new cleanup preview."
        )
    enabled = [
        name
        for name, config in backups.destination_configs().items()
        if config.get("enabled", True)
    ]
    if (
        best
        and enabled
        and not any(
            best.copies.get(name)
            and best.copies[name].status == "completed"
            and copy_current(
                backups,
                best.backup_id,
                name,
                backups.destination_configs()[name],
                value,
            )
            for name in enabled
        )
    ):
        reasons.append("The latest usable backup has no completed external copy.")
    if any(
        item.get("enabled") and (not item.get("available") or item.get("low_space"))
        for item in destinations.values()
    ):
        reasons.append("A backup destination is unavailable or low on free space.")
    if any(
        copy.status == "failed"
        for item in summaries
        for name, copy in item.copies.items()
        if name in enabled
    ):
        reasons.append("A destination copy failed.")
    if value.get("schedule", {}).get("status") in ("failed", "skipped"):
        reasons.append("A scheduled backup failed or was missed.")
    drill = value.get("drill")
    if drill and drill.get("status") in ("failed", "running"):
        reasons.append("The latest isolated recovery drill failed or did not finish.")
    alerts = [
        {
            "id": hashlib.sha256(reason.encode()).hexdigest()[:16],
            "message": reason,
            "server_name": backups.server.server_name,
        }
        for reason in reasons
    ]
    return {
        "readiness": (
            "unavailable" if best is None else "attention" if reasons else "ready"
        ),
        "readiness_reasons": reasons,
        "recovery_backup_id": best.backup_id if best else None,
        "drill": drill,
        "destinations": destinations,
        "alerts": alerts,
    }


async def recovery_drill(
    backups: Any, identifier: str, recovery_key: str | None = None
):
    async with backups.server.operation_lock:
        started = utcnow().isoformat()
        await run_in_thread(
            save_drill,
            backups,
            identifier,
            {"backup_id": identifier, "checked_at": started, "status": "running"},
        )
        try:
            inspected = await backups.inspect_snapshot(identifier, recovery_key)
            components = [
                name
                for name, state in inspected.manifest.components.items()
                if state == "included"
            ]
            plan = await backups.plan_restore(
                identifier, components, recovery_key, dry_run=True
            )
            if not plan.sufficient_space:
                raise BackupRestoreError(
                    "Recovery drill has insufficient staging space."
                )
            record = {
                "backup_id": identifier,
                "checked_at": started,
                "status": "passed",
                "checked_files": plan.checked_files,
            }
        except Exception:
            record = {
                "backup_id": identifier,
                "checked_at": started,
                "status": "failed",
                "error": "Isolated recovery drill failed; inspect recovery readiness.",
            }
            await run_in_thread(save_drill, backups, identifier, record)
            raise
        await run_in_thread(save_drill, backups, identifier, record)
        return record


def save_drill(backups, identifier, record):
    value = backups.catalog.load()
    value["drill"] = record
    value["archives"].setdefault(identifier, {})["drill"] = record
    backups.catalog.save(value)


async def maintain_assurance(backups: Any):
    if backups.server.operation_lock.locked() or backups.server.operation_lock.waiting:
        return False
    async with backups.server.operation_lock:
        return await _maintain_assurance(backups)


async def _maintain_assurance(backups: Any):
    health = await backups.backup_health()
    value = await run_in_thread(backups.catalog.load)
    # Persist active condition IDs; restart and minute polling do not repeat alerts.
    active = {alert["id"] for alert in health.alerts}
    old = set(value.get("active_alerts", []))
    if active != old:
        value["active_alerts"] = sorted(active)
        await run_in_thread(backups.catalog.save, value)
        for alert in health.alerts:
            if alert["id"] not in old:
                from ..events.backup import BackupAttention

                if backups.server.events is not None:
                    await backups.server.events.emit(
                        "backup_attention",
                        BackupAttention(
                            server_name=backups.server.server_name,
                            alert_id=str(alert["id"]),
                            message=str(alert["message"]),
                        ).model_dump(),
                    )
    hours = backups.server.settings.get("backups.recovery_drill_interval_hours", 0)
    previous = value.get("drill", {}).get("checked_at")
    if (
        not hours
        or not health.recovery_backup_id
        or (
            previous
            and utcnow() - datetime.fromisoformat(previous) < timedelta(hours=hours)
        )
    ):
        return False
    if backups.server.operation_lock.waiting:
        return False
    try:
        await recovery_drill(backups, health.recovery_backup_id)
    except Exception:
        backups.logger.warning(
            "Isolated recovery drill needs attention for '%s'.",
            backups.server.server_name,
        )
    return True


def cleanup_preview(backups, name, *, bound=None):
    config, root = bound if bound is not None else destination_root(backups, name)
    value = backups.catalog.load()
    index = value.get("destinations", {}).get(name, {})
    records = (
        index.get("archives", {})
        if index.get("location") == location_id(config)
        else {}
    )
    candidates = []
    for identifier, record in records.items():
        if Path(safe_name(identifier)).name != identifier:
            raise BackupRestoreError("Invalid external archive name.")
        target = root / identifier
        if not target.exists():
            continue
        if (
            target.is_symlink()
            or not target.is_file()
            or digest(target) != record["sha256"]
        ):
            raise BackupRestoreError("An external copy changed; cleanup is blocked.")
        local = value["archives"].get(identifier, record)
        protected = (
            local.get("pinned", False)
            or (local.get("protected_until") or "") > utcnow().isoformat()
        )
        candidates.append((identifier, record, protected))
    candidates.sort(key=lambda item: item[1].get("created_at", ""), reverse=True)
    keep = {item[0] for item in candidates if item[2]}
    count, budget = config.get("keep_count", 0), config.get("storage_budget_bytes", 0)
    keep.update(item[0] for item in candidates[:count] if count)
    if not count:
        keep.update(item[0] for item in candidates)
    if candidates:
        keep.add(candidates[0][0])  # Never delete the newest recorded recovery copy.
    total = sum(item[1]["size"] for item in candidates if item[0] in keep)
    if budget:
        for identifier, record, protected in reversed(candidates):
            if total <= budget:
                break
            if identifier in keep and not protected and identifier != candidates[0][0]:
                keep.remove(identifier)
                total -= record["size"]
    delete = [item[0] for item in candidates if item[0] not in keep]
    token = hashlib.sha256(
        json.dumps([name, config, candidates, sorted(keep)], sort_keys=True).encode()
    ).hexdigest()
    return DestinationCleanupPlan(
        destination=name,
        token=token,
        delete=delete,
        retain=sorted(keep),
        reclaim_bytes=sum(
            record["size"]
            for identifier, record, _ in candidates
            if identifier in delete
        ),
        available_bytes=shutil.disk_usage(root if root.is_dir() else root.parent).free,
        warnings=[
            "Only recorded, unchanged BSM copies are eligible. Pins, safety protection, and the newest recorded copy are retained. Untracked files are never deleted."
        ],
    )


async def cleanup_destination(backups: Any, name: str, token: str | None = None):
    async with backups.server.operation_lock:
        await run_in_thread(reconcile_cleanup, backups, name)
        plan = await run_in_thread(cleanup_preview, backups, name)
        if token is None:
            return plan
        if token != plan.token:
            raise BackupRestoreError(
                "Destination or policy changed. Review a new cleanup preview."
            )
        await run_in_thread(apply_cleanup, backups, name, plan)
        return plan.model_copy(update={"applied": True})


def apply_cleanup(backups, name, plan):
    bound = destination_root(backups, name)
    _, root = bound
    if cleanup_preview(backups, name, bound=bound).token != plan.token:
        raise BackupRestoreError("Destination changed. Review cleanup again.")
    value = backups.catalog.load()
    index = value.get("destinations", {}).get(name, {})
    records = index.get("archives", {})
    # Persist the approved intent before unlinking. A killed process must not
    # cause maintenance to recreate a copy whose deletion already happened.
    index["pending_delete"] = list(plan.delete)
    for identifier in plan.delete:
        copy = value["archives"].get(identifier, {}).get("copies", {}).get(name)
        if copy is not None:
            copy.update(status="pruned", next_retry_at=None)
    backups.catalog.save(value)
    for identifier in plan.delete:
        target = root / identifier
        if target.is_symlink() or digest(target) != records[identifier]["sha256"]:
            raise BackupRestoreError("External copy changed. Review cleanup again.")
        target.unlink()
        records.pop(identifier, None)
        index["pending_delete"].remove(identifier)
        # Mark pruned copies so maintenance does not immediately recreate them.
        copy = value["archives"].get(identifier, {}).get("copies", {}).get(name)
        if copy is not None:
            copy.update(status="pruned", next_retry_at=None)
        backups.catalog.save(value)


def reconcile_cleanup(backups, name):
    """Resolve recorded deletion intent without deleting any additional files."""
    config, root = destination_root(backups, name)
    value = backups.catalog.load()
    index = value.get("destinations", {}).get(name, {})
    pending = index.get("pending_delete", [])
    if not pending or index.get("location") != location_id(config):
        return
    for identifier in pending:
        if Path(safe_name(identifier)).name != identifier:
            raise BackupRestoreError("Invalid external archive name.")
        target = root / identifier
        record = index.get("archives", {}).get(identifier)
        if target.exists():
            if (
                target.is_symlink()
                or record is None
                or digest(target) != record["sha256"]
            ):
                raise BackupRestoreError(
                    "An interrupted cleanup copy changed; preserve it for inspection."
                )
            copy = value["archives"].get(identifier, {}).get("copies", {}).get(name)
            if copy is not None:
                copy.update(status="completed")
        else:
            index.get("archives", {}).pop(identifier, None)
    index["pending_delete"] = []
    backups.catalog.save(value)
