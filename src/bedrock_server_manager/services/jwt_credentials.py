"""Durable signing credentials, isolated from public configuration snapshots."""

import asyncio
import secrets
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

from sqlalchemy import select

from ..backups.credentials import (
    CREDENTIALS_DIR_NAME,
    atomic_bytes,
    locked_credential_file,
    private_directory,
    protect,
)
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


def _parse_key_bytes(data: bytes) -> str:
    if len(data) > 8192:
        raise ValueError("Invalid signing credential")
    text = data.decode("utf-8").strip("\r\n")
    if (
        not 1 <= len(text) <= 4096
        or "\n" in text
        or "\r" in text
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in text)
        or any(ch in "{}" for ch in text)
    ):
        raise ValueError("Invalid signing credential")
    return text


def _read_key(path: Path) -> str:
    if not path.is_file():
        raise ConfigurationError("Signing credential is not a regular file.")
    protect(path)
    with path.open("rb") as stream:
        data = stream.read(8193)
    return _parse_key_bytes(data)


def _write_key(path: Path, key: str) -> None:
    atomic_bytes(path, f"{key}\n".encode("utf-8"))


def _file_key(
    config_dir: str, legacy: str | None, initialized: bool, create: bool
) -> str | None:
    """Serialize initial publication across processes; never replace a live key."""
    with _LOCK:
        root = Path(config_dir)
        directory = private_directory(root / CREDENTIALS_DIR_NAME)
        path = directory / "jwt.key"
        lock_path = directory / ".jwt.key.lock"
        with locked_credential_file(
            lock_path,
            busy_message="Signing credential is busy; retry startup.",
        ):
            if path.exists() or path.is_symlink():
                key = _read_key(path)
                if legacy is not None and key != legacy:
                    raise ConfigurationError(
                        "Signing credential conflicts with the database; restore matching configuration and database."
                    )
                return key
            if initialized:
                raise ConfigurationError(
                    "Signing credential is missing; restore credentials/jwt.key."
                )
            if legacy is None and not create:
                return None
            key = legacy if legacy is not None else secrets.token_urlsafe(32)
            if not isinstance(key, str) or not 1 <= len(key) <= 4096:
                raise ConfigurationError("Legacy signing credential is invalid.")
            _write_key(path, key)
            if _read_key(path) != key:
                raise ConfigurationError("Cannot verify signing credential.")
            return key


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
                "Cannot read or protect signing credential; restore credentials/jwt.key."
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
