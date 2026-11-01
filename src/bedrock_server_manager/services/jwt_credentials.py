"""Durable signing credentials, isolated from public configuration snapshots."""

import asyncio
import json
import os
import secrets
import threading
import time
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any
from weakref import WeakValueDictionary

from sqlalchemy import select

from ..backups.credentials import atomic_json, private_directory, protect
from ..db.models import LoginSession
from ..error import ConfigurationError
from ..state.changeset import ChangeSet
from ..utils.threads import run_in_thread

if TYPE_CHECKING:
    from ..config.settings import Settings

_LOCK = threading.RLock()
_ASYNC_LOCKS: WeakValueDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = (
    WeakValueDictionary()
)
PRIVATE_FIELDS = frozenset({"jwt_secret_key", "jwt_key_initialized"})


def _read_key(path: Path) -> str:
    if not path.is_file():
        raise ConfigurationError("Signing credential is not a regular file.")
    protect(path)
    with path.open("rb") as stream:
        data = stream.read(8193)
    value = json.loads(data)
    if (
        len(data) > 8192
        or not isinstance(value, dict)
        or set(value) != {"version", "secret"}
        or type(value["version"]) is not int
        or value["version"] != 1
        or not isinstance(value["secret"], str)
        or not 1 <= len(value["secret"]) <= 4096
    ):
        raise ValueError("Invalid signing credential")
    return value["secret"]


def _file_key(
    config_dir: str, legacy: str | None, initialized: bool, create: bool
) -> str | None:
    """Serialize initial publication across processes; never replace a live key."""
    with _LOCK:
        directory = private_directory(Path(config_dir) / "security")
        path = directory / "jwt-signing-key.json"
        lock_path = directory / ".jwt-signing-key.lock"
        if lock_path.is_symlink():
            raise ConfigurationError("Private storage must not be a symbolic link.")
        fd = os.open(
            lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        with os.fdopen(fd, "r+b") as stream:
            protect(lock_path)
            if os.name == "nt" and lock_path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            started = time.monotonic()
            while True:
                try:
                    if os.name == "nt":
                        platform_lock: Any = import_module("msvcrt")
                        stream.seek(0)
                        platform_lock.locking(fd, platform_lock.LK_NBLCK, 1)
                    else:
                        platform_lock = import_module("fcntl")
                        platform_lock.flock(
                            fd, platform_lock.LOCK_EX | platform_lock.LOCK_NB
                        )
                    break
                except OSError:
                    if time.monotonic() - started >= 5:
                        raise ConfigurationError(
                            "Signing credential is busy; retry startup."
                        ) from None
                    time.sleep(0.05)
            try:
                if path.exists() or path.is_symlink():
                    key = _read_key(path)
                    if legacy is not None and key != legacy:
                        raise ConfigurationError(
                            "Signing credential conflicts with the database; restore matching configuration and database."
                        )
                    return key
                if initialized:
                    raise ConfigurationError(
                        "Signing credential is missing; restore security/jwt-signing-key.json."
                    )
                if legacy is None and not create:
                    return None
                key = legacy if legacy is not None else secrets.token_urlsafe(32)
                if not isinstance(key, str) or not 1 <= len(key) <= 4096:
                    raise ConfigurationError("Legacy signing credential is invalid.")
                atomic_json(path, {"version": 1, "secret": key})
                if _read_key(path) != key:
                    raise ConfigurationError("Cannot verify signing credential.")
                return key
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    platform_lock.locking(fd, platform_lock.LK_UNLCK, 1)
                else:
                    platform_lock.flock(fd, platform_lock.LOCK_UN)


async def signing_key(settings: "Settings", *, create: bool = True) -> str | None:
    """Migrate once, commit the nonsecret marker, then retain a process-local key."""
    cached = settings._jwt_signing_credential
    if cached is not None:
        return cached
    loop = asyncio.get_running_loop()
    lock = _ASYNC_LOCKS.setdefault(loop, asyncio.Lock())
    async with lock:
        cached = settings._jwt_signing_credential
        if cached is not None:
            return cached
        legacy = settings.get("web.jwt_secret_key")
        initialized = settings.get("web.jwt_key_initialized", False)
        # Even a database from before the initialization marker must never silently
        # replace a missing credential while persisted session families exist.
        if not initialized and legacy is None:
            async with settings.storage.transaction() as session:
                initialized = (
                    await session.scalar(select(LoginSession.id).limit(1)) is not None
                )
        try:
            key = await run_in_thread(
                _file_key, settings.config_dir, legacy, initialized, create
            )
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError(
                "Cannot read or protect signing credential; restore security/jwt-signing-key.json."
            ) from None
        if key is None:
            return None
        changes = ChangeSet()
        changes.add_setting("web.jwt_key_initialized")

        def migrate(candidate):
            if candidate.web.jwt_secret_key not in (None, legacy):
                raise ConfigurationError(
                    "Signing configuration changed during migration; retry startup."
                )
            candidate.set("web.jwt_secret_key", None)
            candidate.set("web.jwt_key_initialized", True)

        # Only remove the old DB value after a durable, protected file was read back.
        await settings.storage.commit_settings(settings.state, changes, migrate)
        settings._jwt_signing_credential = key
        return key
