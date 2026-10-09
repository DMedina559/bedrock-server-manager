"""Validated archive extraction and rollback for content replacement."""

import logging
import os
import shutil
import stat
import tempfile
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

from ..utils.threads import run_in_thread

logger = logging.getLogger(__name__)


def validate_archive(archive: ZipFile) -> None:
    """Reject unsafe names, links, and conflicting entries before writing files."""
    entries: dict[str, bool] = {}
    for member in archive.infolist():
        name = member.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if (
            not name
            or path.is_absolute()
            or ".." in path.parts
            or any(":" in part for part in path.parts)
            or stat.S_ISLNK(member.external_attr >> 16)
        ):
            raise BadZipFile(f"Unsafe archive entry: {member.filename!r}")
        key = str(path)
        if key in entries:
            raise BadZipFile(f"Duplicate archive entry: {member.filename!r}")
        entries[key] = member.is_dir()
    for name in entries:
        for parent in PurePosixPath(name).parents:
            if str(parent) in entries and not entries[str(parent)]:
                raise BadZipFile(f"Conflicting archive entry: {name!r}")


def extract_archive(
    archive: ZipFile, target: str | Path, members: Iterable[ZipInfo] | None = None
) -> None:
    validate_archive(archive)
    for member in archive.infolist() if members is None else members:
        # Normalize Windows separators consistently with validation.
        normalized = member.filename.replace("\\", "/")
        destination = Path(target).joinpath(*PurePosixPath(normalized).parts)
        if member.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)


@asynccontextmanager
async def temporary_directory(parent: str | Path | None = None) -> AsyncIterator[Path]:
    directory: Path | None = None

    def create() -> None:
        nonlocal directory
        directory = Path(tempfile.mkdtemp(prefix="bsm-", dir=parent))

    try:
        await run_in_thread(create)
        assert directory is not None
        yield directory
    finally:
        if directory is not None:
            await run_in_thread(shutil.rmtree, directory)


class FileTransaction:
    """Keep previous content until every replacement has succeeded."""

    def __init__(self, journal: Path):
        self.journal = journal
        self.saved: list[tuple[Path, Path | None]] = []
        self.created_dirs: list[Path] = []

    def mkdir(self, directory: Path) -> None:
        if not directory.exists():
            self.mkdir(directory.parent)
            directory.mkdir()
            self.created_dirs.append(directory)

    def watch(self, target: Path) -> None:
        if any(path == target for path, _ in self.saved):
            return
        backup = self.journal / str(len(self.saved)) if target.exists() else None
        if backup is not None:
            if target.is_dir():
                shutil.copytree(target, backup)
            else:
                shutil.copy2(target, backup)
        self.saved.append((target, backup))

    def retire(self, target: Path) -> None:
        if not target.exists():
            return
        backup = self.journal / str(len(self.saved))
        os.replace(target, backup)
        self.saved.append((target, backup))

    def replace(self, source: Path, target: Path) -> None:
        self.mkdir(target.parent)
        if target.exists():
            self.retire(target)
        else:
            self.saved.append((target, None))
        os.replace(source, target)

    def rollback(self) -> None:
        for target, backup in reversed(self.saved):
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            if backup is not None:
                os.replace(backup, target)
        for directory in reversed(self.created_dirs):
            directory.rmdir()


@asynccontextmanager
async def file_transaction(parent: str | Path) -> AsyncIterator[FileTransaction]:
    journal: Path | None = None

    def create() -> None:
        nonlocal journal
        journal = Path(tempfile.mkdtemp(prefix="bsm-rollback-", dir=parent))

    try:
        await run_in_thread(create)
    except BaseException:
        if journal is not None:
            await run_in_thread(shutil.rmtree, journal)
        raise
    assert journal is not None
    transaction = FileTransaction(journal)
    try:
        yield transaction
    except BaseException:
        try:
            await run_in_thread(transaction.rollback)
        except BaseException:
            logger.exception(
                "Rollback failed; previous content retained at %s", journal
            )
            raise
        await run_in_thread(shutil.rmtree, journal)
        raise
    else:
        await run_in_thread(shutil.rmtree, journal)


def atomic_copy_file(source: str, target: str) -> None:
    destination = Path(target)
    descriptor, name = tempfile.mkstemp(prefix="bsm-copy-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_world_archive(source: str, target: str) -> None:
    destination = Path(target)
    with tempfile.TemporaryDirectory(
        prefix="bsm-export-", dir=destination.parent
    ) as staging:
        archive = shutil.make_archive(
            base_name=str(Path(staging) / "world"),
            format="zip",
            root_dir=source,
            base_dir=".",
        )
        os.replace(archive, destination)
