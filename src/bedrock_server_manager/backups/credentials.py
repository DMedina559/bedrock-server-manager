"""Private host credentials; never included in server settings exports."""

import hashlib
import json
import os
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..error import ConfigurationError

_LOCK = threading.RLock()


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


class BackupCredentials:
    """Keep old keys available for recovery when rotating the active key."""

    def __init__(self, config_dir: str):
        self.directory = Path(config_dir) / "credentials"
        self.path = self.directory / "backup-keys.json"

    def _load(self) -> KeyStore:
        private_directory(self.directory)
        if not self.path.exists():
            return KeyStore()
        protect(self.path)
        try:
            store = KeyStore.model_validate_json(self.path.read_bytes())
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
                raise ValueError
            return store
        except Exception:
            raise ConfigurationError("Cannot read backup credentials.") from None

    def _save(self, store: KeyStore) -> None:
        value = store.model_dump(mode="json")
        for item, record in zip(value["keys"], store.keys):
            item["secret"] = record.secret.get_secret_value()
        atomic_json(self.path, value)

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
