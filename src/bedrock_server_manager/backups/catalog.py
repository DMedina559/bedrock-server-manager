"""Private recovery metadata, verified retention, and mounted storage destinations."""

import json
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from .credentials import BackupCredentials
    from .models import BackupSummary

from ..error import BackupRestoreError
from ..events.backup import BackupActivity
from ..results import CleanupResult
from ..utils.files import temporary_directory
from ..utils.threads import check_cancellation, copy_stream, run_in_thread
from .archive import digest, safe_name
from .credentials import atomic_json, private_directory
from .models import (
    BackupHealth,
    BackupVerification,
    RestoreFileChange,
    RestoreValueChange,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BackupDestination(Protocol):
    """A destination publishes a complete immutable archive or reports failure."""

    def publish(self, source: Path, server_name: str) -> None: ...


class DirectoryDestination:
    """Copy unchanged archives to an administrator-configured mounted directory."""

    def __init__(self, directory: str):
        self.directory = Path(directory)

    def publish(
        self,
        source: Path,
        server_name: str,
        cancellation_event: threading.Event | None = None,
    ) -> None:
        safe_name(server_name)
        if Path(server_name).name != server_name or not self.directory.is_absolute():
            raise BackupRestoreError("Destination requires an absolute directory.")
        # The mount must already exist; never silently create a missing mount point.
        if not self.directory.is_dir():
            raise BackupRestoreError("Destination is unavailable.")
        root = private_directory(self.directory / server_name)
        if root.resolve() == source.parent.resolve():
            raise BackupRestoreError("Destination must differ from local storage.")
        target = root / source.name
        if target.exists():
            if target.is_symlink() or digest(target, cancellation_event) != digest(
                source, cancellation_event
            ):
                raise BackupRestoreError("Destination already has different content.")
            return
        descriptor, temporary = tempfile.mkstemp(prefix=".bsm-copy-", dir=root)
        try:
            with os.fdopen(descriptor, "wb") as output, source.open("rb") as stream:
                copy_stream(stream, output, cancellation_event)
                output.flush()
                os.fsync(output.fileno())
            if digest(Path(temporary), cancellation_event) != digest(
                source, cancellation_event
            ):
                raise BackupRestoreError("Destination copy verification failed.")
            check_cancellation(cancellation_event)
            os.replace(temporary, target)
            if os.name != "nt":
                descriptor = os.open(root, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            Path(temporary).unlink(missing_ok=True)


class BackupCatalog:
    """Store metadata separately from portable archives; never store file values or keys."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.path = directory / ".catalog.json"

    def load(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "archives": {}}
        if self.path.is_symlink():
            raise BackupRestoreError("Backup catalog must not be a symbolic link.")
        try:
            value = json.loads(self.path.read_bytes())
            if value.get("version") != 1 or not isinstance(value.get("archives"), dict):
                raise ValueError
            return cast(dict, value)
        except (ValueError, AttributeError):
            raise BackupRestoreError(
                "Backup catalog is unreadable; preserve it for recovery."
            ) from None

    def save(self, value: dict) -> None:
        private_directory(self.directory)
        atomic_json(self.path, value)

    def update(self, identifier: str, **metadata) -> None:
        value = self.load()
        value["archives"].setdefault(identifier, {}).update(metadata)
        self.save(value)


class ManagedBackups:
    """Additional workflows mixed into the server's unified backup service."""

    # Concrete implementation supplies these capabilities through UnifiedServerBackups.
    server: Any
    logger: Any
    if TYPE_CHECKING:

        def _directory(self) -> str:
            raise NotImplementedError

        def resolve_backup(self, identifier: str) -> Path:
            raise NotImplementedError

        def _password(self, path: Path, supplied: str | None) -> str | None:
            raise NotImplementedError

        def unpack_snapshot(
            self, path: Path, destination: Path, password: str | None = None
        ):
            raise NotImplementedError

        @property
        def credentials(self) -> BackupCredentials:
            raise NotImplementedError

        async def list_snapshots(self) -> list[BackupSummary]:
            raise NotImplementedError

        def _component_target(self, component, name: str) -> Path: ...

        def _safe_target(self, name: str) -> Path:
            raise NotImplementedError

        @staticmethod
        def _check_tree(source: Path) -> None:
            raise NotImplementedError

    async def _notify_backup(self, identifier, action, status, destination=None):
        if self.server.events is not None:
            try:
                await self.server.events.emit(
                    "backup_activity",
                    BackupActivity(
                        server_name=self.server.server_name,
                        backup_id=identifier,
                        action=action,
                        status=status,
                        destination=destination,
                    ).model_dump(),
                )
            except Exception:
                self.logger.warning("Backup observation could not be delivered.")

    @property
    def catalog(self) -> BackupCatalog:
        return BackupCatalog(Path(self._directory()))

    def _record_verified(self, path, manifest, *, verified=True) -> None:
        self.catalog.update(
            path.name,
            verification={
                "status": "verified" if verified else "unverified",
                "verified_at": now() if verified else None,
                "error": None,
            },
            sha256=digest(path),
            fingerprint=[path.stat().st_size, path.stat().st_mtime_ns],
            created_at=manifest.created_at.isoformat(),
            purpose=manifest.reason,
            capture_validated=True,
        )

    async def delete_snapshot(self, identifier):
        """Delete an unprotected local archive; external copies remain independent."""
        async with self.server.operation_lock:
            from .recovery import RestoreJournal

            RestoreJournal(self.server).ensure_clear()
            path = self.resolve_backup(identifier)
            value = await run_in_thread(self.catalog.load)
            record = value["archives"].get(path.name, {})
            if record.get("pinned") or (
                record.get("protected_until") and record["protected_until"] > now()
            ):
                raise BackupRestoreError(
                    "Unpin this backup and wait for its safety protection to expire before deleting it."
                )
            await run_in_thread(path.unlink)
            value["archives"].pop(path.name, None)
            await run_in_thread(self.catalog.save, value)
            await self._notify_backup(path.name, "delete", "completed")

    async def verify_snapshot(
        self, identifier, recovery_key=None, *, record_failure=True
    ):
        """Extract and authenticate in isolation, then validate restorable structures."""
        async with self.server.operation_lock:
            path = self.resolve_backup(identifier)
            try:
                password = await run_in_thread(self._password, path, recovery_key)
                async with temporary_directory(
                    prefix=".bsm-verify-", parent=path.parent
                ) as directory:
                    staging = Path(directory)
                    manifest = await run_in_thread(
                        self.unpack_snapshot, path, staging, password
                    )
                    await run_in_thread(
                        self._validate_recovery_contents, staging, manifest
                    )
                await run_in_thread(self._record_verified, path, manifest)
            except Exception:
                if record_failure:
                    await run_in_thread(
                        self.catalog.update,
                        identifier,
                        fingerprint=[path.stat().st_size, path.stat().st_mtime_ns],
                        verification={
                            "status": "failed",
                            "verified_at": now(),
                            "error": "Archive authentication or recovery validation failed.",
                        },
                    )
                if record_failure:
                    await self._notify_backup(identifier, "verify", "failed")
                raise
            await self._notify_backup(identifier, "verify", "completed")
            return BackupVerification(status="verified", verified_at=now())

    @staticmethod
    def _validate_recovery_contents(staging, manifest):
        from .models import PREFIXES, ServerSettingsExport

        if manifest.components["world"] == "included" and not any(
            (staging / "world" / name).is_file() for name in ("level.dat", "level.txt")
        ):
            raise BackupRestoreError("Backup world metadata is missing.")
        if manifest.components["server.properties"] == "included":
            from .server import UnifiedServerBackups

            UnifiedServerBackups._read_world(staging / PREFIXES["server.properties"])
        for component in ("allowlist.json", "permissions.json"):
            if manifest.components[component] == "included" and not isinstance(
                json.loads((staging / PREFIXES[component]).read_bytes()), list
            ):
                raise BackupRestoreError("Invalid player access configuration.")
        if manifest.components["bsm_settings"] == "included":
            ServerSettingsExport.model_validate_json(
                (staging / PREFIXES["bsm_settings"]).read_bytes()
            )

    async def annotate_snapshot(self, identifier, label=None, notes=None):
        async with self.server.operation_lock:
            self.resolve_backup(identifier)
            updates = {}
            if label is not None:
                if len(label) > 120:
                    raise BackupRestoreError(
                        "Backup labels are limited to 120 characters."
                    )
                updates["label"] = label
            if notes is not None:
                if len(notes) > 2000:
                    raise BackupRestoreError(
                        "Backup notes are limited to 2,000 characters."
                    )
                updates["notes"] = notes
            await run_in_thread(self.catalog.update, identifier, **updates)

    async def pin_snapshot(self, identifier: str, pinned: bool):
        async with self.server.operation_lock:
            self.resolve_backup(identifier)
            await run_in_thread(self.catalog.update, identifier, pinned=pinned)

    def destination_configs(self) -> dict:
        return {
            name: config.model_dump() if hasattr(config, "model_dump") else config
            for name, config in self.server.settings.get(
                "backups.destinations", {}
            ).items()
        }

    async def copy_snapshot(
        self, identifier: str, destination: str, *, automatic=False
    ):
        async with self.server.operation_lock:
            configured = self.destination_configs()
            item = configured.get(destination)
            if not item or not item.get("enabled", True):
                raise BackupRestoreError("Backup destination is not enabled.")
            path = self.resolve_backup(identifier)
            value = await run_in_thread(self.catalog.load)
            copies = value["archives"].get(identifier, {}).get("copies", {})
            previous = copies.get(destination, {})
            attempts = previous.get("attempts", 0) if automatic else 0
            copies[destination] = {"status": "pending", "attempts": attempts + 1}
            await run_in_thread(self.catalog.update, identifier, copies=copies)
            from .assurance import remember_copy

            try:
                await run_in_thread(
                    DirectoryDestination(item["path"]).publish,
                    path,
                    self.server.server_name,
                )
                await run_in_thread(remember_copy, self, identifier, destination, path)
                copies[destination] = {
                    "status": "completed",
                    "completed_at": now(),
                    "attempts": attempts + 1,
                }
            except Exception:
                copies[destination] = {
                    "status": "failed",
                    "attempts": attempts + 1,
                    "next_retry_at": (
                        datetime.now(timezone.utc)
                        + timedelta(seconds=min(3600, 60 * 2 ** (attempts + 1)))
                    ).isoformat(),
                    "error": "Destination copy failed; check availability and free space.",
                }
                await run_in_thread(self.catalog.update, identifier, copies=copies)
                await self._notify_backup(identifier, "copy", "failed", destination)
                raise BackupRestoreError(
                    "Local backup is safe, but its destination copy failed."
                ) from None
            await run_in_thread(self.catalog.update, identifier, copies=copies)
            await self._notify_backup(identifier, "copy", "completed", destination)

    async def backup_health(self) -> BackupHealth:
        async with self.server.operation_lock:
            summaries = await self.list_snapshots()
            value = await run_in_thread(self.catalog.load)
            entries = [value["archives"].get(item.backup_id, {}) for item in summaries]
            keys = await run_in_thread(self.credentials.metadata)
            known = {item["key_id"] for item in keys["keys"]}
            used = {item.key_id for item in summaries if item.encrypted and item.key_id}
            from .assurance import readiness
            from .schedule import status

            assurance = await run_in_thread(readiness, self, summaries, value, known)
            return BackupHealth(
                **assurance,
                schedule=status(self, value),
                count=len(summaries),
                total_bytes=sum(item.size for item in summaries),
                last_success_at=max(
                    (e.get("created_at", "") for e in entries), default=""
                )
                or None,
                last_verified_at=max(
                    (
                        e.get("verification", {}).get("verified_at", "")
                        for e in entries
                        if e.get("verification", {}).get("status") == "verified"
                    ),
                    default="",
                )
                or None,
                last_failure_at=value.get("last_failure_at"),
                last_error=value.get("last_error"),
                unverified_count=sum(
                    i.verification.status == "unverified" for i in summaries
                ),
                failed_count=sum(
                    i.error is not None or i.verification.status == "failed"
                    for i in summaries
                ),
                missing_key_ids=sorted(used - known),
                older_key_ids=sorted(used - {keys["active"]}),
                destination_failures=sum(
                    copy.status not in ("completed", "pruned")
                    for i in summaries
                    for name, copy in i.copies.items()
                    if name in self.destination_configs()
                    and self.destination_configs()[name].get("enabled", True)
                ),
                verification_interval_hours=self.server.settings.get(
                    "backups.verification_interval_hours", 0
                ),
            )

    async def maintain_backups(self):
        """Perform one bounded unit, leaving queued interactive work first in line."""
        if self.server.operation_lock.locked() or self.server.operation_lock.waiting:
            return
        from .assurance import maintain_assurance

        if await maintain_assurance(self):
            return
        interval = self.server.settings.get("backups.verification_interval_hours", 0)
        # Listing releases its lock before any expensive work starts.
        summaries = await self.list_snapshots()
        for item in summaries:
            if (
                self.server.operation_lock.locked()
                or self.server.operation_lock.waiting
            ):
                return
            due = item.verification.verified_at is None or (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(item.verification.verified_at)
            ) >= timedelta(hours=interval)
            if interval and due:
                try:
                    await self.verify_snapshot(item.backup_id)
                except Exception:
                    self.logger.warning(
                        "Periodic backup verification needs attention for '%s'.",
                        item.filename,
                    )
                return
            for name, config in self.destination_configs().items():
                from .assurance import copy_current

                copy = item.copies.get(name)
                current = await run_in_thread(
                    copy_current,
                    self,
                    item.backup_id,
                    name,
                    config,
                    await run_in_thread(self.catalog.load),
                )
                due_copy = (
                    copy is None
                    or (copy.status == "completed" and not current)
                    or (
                        copy.status not in ("completed", "pruned")
                        and copy.attempts < 3
                        and (
                            copy.next_retry_at is None
                            or datetime.now(timezone.utc)
                            >= datetime.fromisoformat(copy.next_retry_at)
                        )
                    )
                )
                if config.get("enabled", True) and due_copy:
                    try:
                        await self.copy_snapshot(item.backup_id, name, automatic=True)
                    except Exception:
                        self.logger.warning(
                            "Backup destination retry needs attention for '%s'.",
                            item.filename,
                        )
                    return

    async def prune_managed_snapshots(self) -> CleanupResult:
        async with self.server.operation_lock:
            from .recovery import RestoreJournal

            if RestoreJournal(self.server).path.exists():
                return CleanupResult(
                    retained=[i.filename for i in await self.list_snapshots()]
                )
            files = [i for i in await self.list_snapshots() if i.error is None]
            count = self.server.settings.get("retention.backups", 3)
            if count == 0:
                return CleanupResult(retained=[i.filename for i in files])
            value = await run_in_thread(self.catalog.load)
            metadata = value["archives"]
            ordered = sorted(
                files,
                key=lambda i: metadata.get(i.filename, {}).get(
                    "created_at", i.filename
                ),
                reverse=True,
            )
            retained = {i.filename for i in ordered[:count]}
            retained.update(
                i.filename for i in ordered if i.verification.status == "failed"
            )
            current = now()
            retained.update(
                i.filename
                for i in ordered
                if i.pinned or (i.protected_until and i.protected_until > current)
            )
            for kind, setting in (
                ("day", "keep_daily"),
                ("week", "keep_weekly"),
                ("month", "keep_monthly"),
            ):
                buckets: set[str] = set()
                limit = self.server.settings.get("backups." + setting, 0)
                for item in ordered:
                    stamp = metadata.get(item.filename, {}).get("created_at")
                    if not stamp or len(buckets) >= limit:
                        continue
                    date = datetime.fromisoformat(stamp)
                    bucket = date.strftime(
                        "%Y-%m-%d"
                        if kind == "day"
                        else "%G-%V" if kind == "week" else "%Y-%m"
                    )
                    if bucket not in buckets:
                        retained.add(item.filename)
                        buckets.add(bucket)
            budget = self.server.settings.get("backups.storage_budget_bytes", 0)
            if len(retained) == len(ordered) and (
                not budget or sum(i.size for i in ordered) <= budget
            ):
                return CleanupResult(retained=sorted(retained))
            # Require an unchanged validated capture or a verified recovery point.
            # Retention never initiates expensive full extraction implicitly.
            usable = None
            for item in ordered:
                try:
                    record = metadata.get(item.filename, {})
                    trusted = (
                        item.verification.status == "verified"
                        or (
                            record.get("capture_validated", False)
                            and item.verification.status != "failed"
                        )
                    ) and record.get("sha256") == await run_in_thread(
                        digest, self.resolve_backup(item.filename)
                    )
                    if not trusted:
                        continue
                    usable = item.filename
                    retained.add(usable)
                    break
                except Exception:
                    retained.add(item.filename)
            if usable is None:
                return CleanupResult(retained=[i.filename for i in files])
            budget = self.server.settings.get("backups.storage_budget_bytes", 0)
            protected = {
                i.filename
                for i in ordered
                if i.pinned
                or i.verification.status == "failed"
                or (i.protected_until and i.protected_until > current)
            } | {usable}
            if budget:
                total = sum(i.size for i in ordered if i.filename in retained)
                for item in reversed(ordered):
                    if total <= budget:
                        break
                    if item.filename in retained and item.filename not in protected:
                        retained.remove(item.filename)
                        total -= item.size
            deleted, failures = [], {}
            for item in ordered:
                if item.filename in retained:
                    continue
                try:
                    await run_in_thread(self.resolve_backup(item.filename).unlink)
                    deleted.append(item.filename)
                    metadata.pop(item.filename, None)
                except OSError:
                    from ..failures import classify_failure

                    failures[item.filename] = classify_failure(
                        OSError("Backup could not be removed.")
                    ).error
            # Reload updates made by verification before removing deleted records.
            value = await run_in_thread(self.catalog.load)
            for filename in deleted:
                value["archives"].pop(filename, None)
            await run_in_thread(self.catalog.save, value)
            return CleanupResult(
                deleted=deleted, retained=sorted(retained), failures=failures
            )

    def restore_comparison(self, staging, targets):
        from .models import PREFIXES
        from .recovery import settings_export

        changes, settings, counts = [], [], {"added": 0, "replaced": 0, "removed": 0}
        for component, name in targets.items():
            if component == "bsm_settings":
                before = settings_export(self.server).model_dump(mode="json")
                after = json.loads((staging / PREFIXES[component]).read_bytes())
                for key in ("autostart", "autoupdate", "target_version", "custom"):
                    if before.get(key) != after.get(key):
                        settings.append(
                            RestoreValueChange(
                                component=component,
                                key=key,
                                before=(
                                    "[redacted]"
                                    if key == "custom"
                                    else str(before.get(key))
                                ),
                                after=(
                                    "[redacted]"
                                    if key == "custom"
                                    else str(after.get(key))
                                ),
                            )
                        )
                continue
            source, target = staging / PREFIXES[component], self._component_target(
                component, name
            )
            if component == "server_directory":
                from .selection import server_entries

                for entry in server_entries(target):
                    self._check_tree(entry)
            elif target.exists():
                self._check_tree(target)

            def files(root):
                if not root.exists():
                    return {}
                return (
                    {
                        p.relative_to(root).as_posix(): p
                        for p in root.rglob("*")
                        if component != "server_directory"
                        or not p.relative_to(root).parts[0].startswith(".bsm-")
                        if p.is_file()
                    }
                    if root.is_dir()
                    else {"": root}
                )

            old, new = files(target), files(source)
            for relative in sorted(old.keys() | new.keys()):
                action = (
                    "added"
                    if relative not in old
                    else (
                        "removed"
                        if relative not in new
                        else (
                            "replaced"
                            if digest(old[relative]) != digest(new[relative])
                            else None
                        )
                    )
                )
                if action:
                    counts[action] += 1
                    if len(changes) < 1000:
                        changes.append(
                            RestoreFileChange(
                                component=component,
                                path=name + ("/" + relative if relative else ""),
                                action=action,
                            )
                        )
            if component in ("permissions.json", "allowlist.json"):
                try:
                    before = json.loads(target.read_bytes()) if target.exists() else []
                except (ValueError, UnicodeError):
                    before = None
                after = json.loads(source.read_bytes())
                if before != after:
                    settings.append(
                        RestoreValueChange(
                            component=component,
                            key=(
                                "player access"
                                if component == "allowlist.json"
                                else "operator permissions"
                            ),
                            before=(
                                f"{len(before)} entries (values hidden)"
                                if isinstance(before, list)
                                else "Invalid current JSON (values hidden)"
                            ),
                            after=f"{len(after)} entries (values hidden)",
                        )
                    )
            if component == "server.properties":

                def properties(path):
                    if not path.exists():
                        return {}
                    return dict(
                        line.split("=", 1)
                        for line in path.read_text(encoding="utf-8-sig").splitlines()
                        if "=" in line and not line.lstrip().startswith("#")
                    )

                before, after = properties(target), properties(source)
                public = {
                    "server-name",
                    "gamemode",
                    "difficulty",
                    "level-name",
                    "max-players",
                    "server-port",
                    "server-portv6",
                    "allow-cheats",
                    "online-mode",
                    "allow-list",
                    "view-distance",
                    "tick-distance",
                }
                for key in sorted(before.keys() | after.keys()):
                    if before.get(key) != after.get(key):
                        settings.append(
                            RestoreValueChange(
                                component=component,
                                key=key,
                                before=(
                                    before.get(key) if key in public else "[redacted]"
                                ),
                                after=after.get(key) if key in public else "[redacted]",
                            )
                        )
        return changes, counts, settings
