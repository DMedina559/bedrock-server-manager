"""Metadata-only observations for manual and periodic backup work."""

from typing import Literal

from .models import EventDefinition, EventModel
from .registry import builtin_events


class BackupActivity(EventModel):
    server_name: str
    backup_id: str
    action: Literal["capture", "verify", "copy"]
    status: Literal["completed", "failed"]
    destination: str | None = None


builtin_events.register(
    EventDefinition(
        name="backup_activity",
        phase="after",
        identity_keys=("server_name", "backup_id", "action"),
        description="Backup capture, verification, or destination copy outcome; no credentials or file values.",
    ),
    BackupActivity,
)
