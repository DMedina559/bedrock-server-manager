"""Write-ahead restore journal spanning files and one server settings record."""

import json
import os
import shutil
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from ..error import BackupRestoreError
from ..utils.threads import check_cancellation
from .archive import safe_name
from .credentials import atomic_json, private_directory
from .models import PACK_COMPONENTS, ServerSettingsExport
from .work import FileWork, tree_paths

if TYPE_CHECKING:
    from ..core.bedrock_server import BedrockServer


def remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def sync_tree(
    path: Path,
    cancellation_event: threading.Event | None = None,
    *,
    stage_callback=None,
    include_files: bool = True,
) -> None:
    """Flush replacement files, or only directories after durable writes."""
    work = FileWork(
        "Flushing restore files" if include_files else "Flushing restore directories",
        stage_callback,
    )
    status = "failed"
    try:
        work.progress(force=True)
        with work.phase("metadata"):
            paths = list(tree_paths(path, cancellation_event))
        for item in paths if include_files else ():
            check_cancellation(cancellation_event)
            with work.phase("metadata"):
                metadata = item.stat()
                regular = item.is_file()
            if regular:
                with work.phase("open"):
                    stream = item.open("r+b")
                try:
                    with work.phase("fsync"):
                        os.fsync(stream.fileno())
                finally:
                    with work.phase("close"):
                        stream.close()
                work.files += 1
                work.bytes += metadata.st_size
            work.progress()
        if os.name != "nt":
            for item in reversed(paths):
                check_cancellation(cancellation_event)
                with work.phase("metadata"):
                    directory = item.is_dir()
                if directory:
                    with work.phase("directory_open"):
                        descriptor = os.open(item, os.O_RDONLY)
                    try:
                        with work.phase("directory_fsync"):
                            os.fsync(descriptor)
                    finally:
                        with work.phase("directory_close"):
                            os.close(descriptor)
                work.progress()
        work.progress(force=True)
        status = "completed"
    finally:
        work.finish(status)


async def apply_settings(
    server: "BedrockServer", settings: ServerSettingsExport, commit=None
) -> None:
    from ..services.server_service import ServerService

    if server.state is None or server.storage is None:
        raise BackupRestoreError("Persistent server settings are unavailable.")
    import asyncio

    from ..state.updates import ServerUpdate
    from ..utils.threads import run_in_thread

    async def before_publish():
        if commit is not None:
            await run_in_thread(commit)

    update = ServerUpdate(
        server_name=server.server_name,
        **settings.model_dump(exclude={"schema_version"}),
    )
    task = asyncio.create_task(
        ServerService(server.state, server.storage).apply_update(
            update, before_publish=before_publish
        )
    )
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        task.result()
        raise


def settings_export(server: "BedrockServer") -> ServerSettingsExport:
    return ServerSettingsExport.model_validate(
        server.configuration.snapshot().model_dump(
            include={"autostart", "autoupdate", "target_version", "custom"}
        )
    )


class RestoreJournal:
    """Record intent before each rename; rollback is safe to repeat after a crash."""

    def __init__(self, server: "BedrockServer"):
        self.server = server
        self.root = Path(server.paths.server_dir)
        self.path = self.root / ".bsm-restore"
        self.record = self.path / "journal.json"

    def ensure_clear(self) -> None:
        if self.path.exists() or self.path.is_symlink():
            raise BackupRestoreError(
                "An unfinished restore requires recovery before modifying this server."
            )

    def begin(
        self, targets: list[str], restore_settings: bool, full_directory: bool = False
    ) -> None:
        self.ensure_clear()
        private_directory(self.path)
        state = {
            "version": 1,
            "full_directory": full_directory,
            "server_name": self.server.server_name,
            "committed": False,
            "settings": (
                settings_export(self.server).model_dump(mode="json")
                if restore_settings
                else None
            ),
            "entries": [
                {
                    "target": safe_name(name),
                    "existed": (self.root / name).exists(),
                    "started": False,
                    "rolled_back": False,
                }
                for name in targets
            ],
        }
        atomic_json(self.record, state)

    def _load(self):
        if self.path.is_symlink() or self.record.is_symlink():
            raise BackupRestoreError(
                "Recovery storage must not contain symbolic links."
            )
        state = json.loads(self.record.read_bytes())
        if (
            state.get("version") != 1
            or state.get("server_name") != self.server.server_name
        ):
            raise BackupRestoreError("Invalid restore recovery journal.")
        for entry in state["entries"]:
            name = safe_name(entry["target"])
            if (
                name
                not in (
                    "server.properties",
                    "allowlist.json",
                    "permissions.json",
                    "config",
                    *PACK_COMPONENTS,
                )
                and not (name.startswith("worlds/") and len(Path(name).parts) == 2)
                and not (
                    state.get("full_directory") is True
                    and len(Path(name).parts) == 1
                    and not name.casefold().startswith(".bsm-")
                )
            ):
                raise BackupRestoreError("Invalid recovery destination.")
            target = self.root / name
            if target.resolve() != self.root.resolve().joinpath(*Path(name).parts):
                raise BackupRestoreError("Recovery destination contains a link.")
        return state

    def replace(self, index: int, source: Path | None) -> None:
        state = self._load()
        entry = state["entries"][index]
        target = self.root / entry["target"]
        saved = self.path / str(index)
        entry["started"] = True
        atomic_json(self.record, state)
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry["existed"]:
            os.replace(target, saved)
        if source is not None:
            os.replace(source, target)
        # Directory renames and journal writes must reach disk before commit.
        if os.name != "nt":
            for folder in (target.parent, self.path):
                fd = os.open(folder, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)

    def commit(self) -> None:
        state = self._load()
        state["committed"] = True
        atomic_json(self.record, state)

    async def recover(self) -> None:
        from ..utils.threads import run_in_thread

        if not await run_in_thread(self.path.exists):
            return
        state = await run_in_thread(self._load)
        if state["committed"]:
            if state["settings"] is not None:
                if self.server.storage is None:
                    raise BackupRestoreError(
                        "Persistent settings are unavailable for recovery."
                    )
                async with self.server.storage.transaction() as session:
                    record = await self.server.storage.server_repo.get_server_by_name(
                        session, self.server.server_name
                    )
                    if record is None:
                        raise BackupRestoreError(
                            "The restored server settings record is missing."
                        )
                    exported = ServerSettingsExport(
                        autostart=bool(record.autostart),
                        autoupdate=bool(record.autoupdate),
                        target_version=record.target_version or "UNKNOWN",
                        custom=record.custom if isinstance(record.custom, dict) else {},
                    )
                await apply_settings(self.server, exported)
            await run_in_thread(shutil.rmtree, self.path)
            return
        if await self.server.is_running():
            raise BackupRestoreError(
                "Stop the server before recovering its interrupted restore."
            )
        # Restore the durable settings first. A crash retries this idempotently.
        if state["settings"] is not None:
            try:
                exported = ServerSettingsExport.model_validate(state["settings"])
            except ValueError:
                raise BackupRestoreError(
                    "Invalid recovery settings; preserve the journal for inspection."
                ) from None
            await apply_settings(self.server, exported)
        await run_in_thread(self._rollback_files, state)
        await run_in_thread(shutil.rmtree, self.path)

    def _rollback_files(self, state) -> None:
        for index in reversed(range(len(state["entries"]))):
            entry = state["entries"][index]
            if not entry["started"] or entry["rolled_back"]:
                continue
            target = self.root / entry["target"]
            saved = self.path / str(index)
            if entry["existed"] and saved.exists():
                # Copy the old data while preserving the journal's recovery copy.
                restored = self.path / f"restore-{index}"
                remove(restored)
                if saved.is_dir():
                    shutil.copytree(saved, restored)
                else:
                    shutil.copy2(saved, restored)
                sync_tree(restored)
                remove(target)
                os.replace(restored, target)
            elif not entry["existed"]:
                remove(target)
            if os.name != "nt":
                # Persist both sides of a rollback rename before its completion marker.
                for folder in (target.parent, self.path):
                    descriptor = os.open(folder, os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
            entry["rolled_back"] = True
            atomic_json(self.record, state)
