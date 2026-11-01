"""Private host credentials; never included in server settings exports."""

import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..error import ConfigurationError

_LOCK = threading.RLock()
CREDENTIALS_DIR_NAME = "credentials"
BACKUP_KEYRING_HEADER = "# BSM-KEYRING-V1"


def protect(path: Path, *, directory: bool = False) -> None:
    """Restrict a private path to the service identity and host administrators."""
    if path.is_symlink():
        raise ConfigurationError("Private storage must not be a symbolic link.")
    if os.name != "nt":
        path.chmod(0o700 if directory else 0o600)
        return
    import ntsecuritycon
    import win32api
    import win32con
    import win32security

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
    )
    try:
        owner = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()
    acl = win32security.ACL()
    flags = (
        (win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE)
        if directory
        else 0
    )
    for sid in (
        owner,
        win32security.CreateWellKnownSid(
            win32security.WinBuiltinAdministratorsSid, None
        ),
        win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None),
    ):
        acl.AddAccessAllowedAceEx(
            win32security.ACL_REVISION, flags, ntsecuritycon.FILE_ALL_ACCESS, sid
        )
    win32security.SetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION
        | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )


def private_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    protect(path, directory=True)
    return path


def credentials_directory(config_dir: str | Path) -> Path:
    """Return the canonical private directory for all host secret `.key` files."""
    return private_directory(Path(config_dir) / CREDENTIALS_DIR_NAME)


def atomic_bytes(path: Path, data: bytes) -> None:
    """Durably replace a private credential file without following its symlink."""
    if path.is_symlink():
        raise ConfigurationError("Private storage must not be a symbolic link.")
    descriptor, name = tempfile.mkstemp(prefix=".bsm-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            protect(temporary)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        protect(path)
        if os.name != "nt":
            folder = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: Any) -> None:
    """Durably replace a private JSON document without following its symlink."""
    if path.is_symlink():
        raise ConfigurationError("Private storage must not be a symbolic link.")
    descriptor, name = tempfile.mkstemp(prefix=".bsm-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            protect(temporary)
            json.dump(value, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            folder = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def locked_credential_file(
    lock_path: Path,
    *,
    busy_message: str = "Credential store is busy; retry startup.",
) -> Iterator[None]:
    """Serialize initial creation or migration of a private `.key` file across processes."""
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
                    raise ConfigurationError(busy_message) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                platform_lock.locking(fd, platform_lock.LK_UNLCK, 1)
            else:
                platform_lock.flock(fd, platform_lock.LOCK_UN)


def key_id(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:24]


class KeyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key_id: str
    created_at: str
    secret: SecretStr


class KeyStore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    active: str | None = None
    keys: list[KeyRecord] = Field(default_factory=list)


def _parse_keyring_bytes(raw: bytes) -> KeyStore:
    text = raw.decode("utf-8").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith(BACKUP_KEYRING_HEADER):
        raise ValueError("Invalid backup key file header")
    header = lines[0].removeprefix(BACKUP_KEYRING_HEADER).strip()
    active: str | None = None
    if header:
        if not header.startswith("active="):
            raise ValueError("Invalid backup key header attribute")
        active = header.removeprefix("active=").strip() or None
    records: list[KeyRecord] = []
    for line in lines[1:]:
        if line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError("Invalid backup key record")
        identifier, created_at, secret = parts
        records.append(
            KeyRecord(
                key_id=identifier,
                created_at=created_at,
                secret=SecretStr(secret),
            )
        )
    return KeyStore(version=1, active=active, keys=records)


def _serialize_keyring(store: KeyStore) -> bytes:
    active = store.active or ""
    lines = [f"{BACKUP_KEYRING_HEADER} active={active}"]
    for record in store.keys:
        lines.append(
            f"{record.key_id} {record.created_at} {record.secret.get_secret_value()}"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


class BackupCredentials:
    """Keep old keys available for recovery when rotating the active key."""

    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self.directory = self.config_dir / CREDENTIALS_DIR_NAME
        self.path = self.directory / "backup.key"

    def _validate_store(self, store: KeyStore) -> KeyStore:
        if (
            store.version != 1
            or len({item.key_id for item in store.keys}) != len(store.keys)
            or any(
                key_id(item.secret.get_secret_value()) != item.key_id
                for item in store.keys
            )
            or store.active is not None
            and store.active not in {item.key_id for item in store.keys}
        ):
            raise ValueError("Invalid backup credential store")
        return store

    def _load(self) -> KeyStore:
        private_directory(self.directory)
        if not self.path.exists():
            return KeyStore()
        protect(self.path)
        try:
            return self._validate_store(_parse_keyring_bytes(self.path.read_bytes()))
        except Exception:
            raise ConfigurationError("Cannot read backup credentials.") from None

    def _save(self, store: KeyStore) -> None:
        atomic_bytes(self.path, _serialize_keyring(store))

    def rotate(self) -> KeyRecord:
        with _LOCK:
            store = self._load()
            secret = secrets.token_urlsafe(32)
            record = KeyRecord(
                key_id=key_id(secret),
                secret=SecretStr(secret),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            store.keys.append(record)
            store.active = record.key_id
            self._save(store)
            return record

    def get(self, identifier: str | None = None) -> KeyRecord:
        with _LOCK:
            store = self._load()
            selected = identifier or store.active
            for record in store.keys:
                if record.key_id == selected:
                    return record
        raise ConfigurationError(
            "Backup recovery key is not configured or is unavailable."
        )

    def metadata(self) -> dict[str, Any]:
        with _LOCK:
            store = self._load()
            return {
                "active": store.active,
                "keys": [
                    {"key_id": item.key_id, "created_at": item.created_at}
                    for item in store.keys
                ],
            }

    def emergency_kit(self, identifier: str | None = None) -> str:
        record = self.get(identifier)
        return (
            "BSM backup emergency kit\n\n"
            f"Key ID: {record.key_id}\nCreated: {record.created_at}\n"
            f"Recovery key: {record.secret.get_secret_value()}\n\n"
            "Store this separately from the BSM host. Older backups require their original key.\n"
            "In BSM, upload or select the backup and enter this recovery key.\n"
            "Offline: bedrock-server-manager backup extract BACKUP DESTINATION --recovery-key\n"
        )
