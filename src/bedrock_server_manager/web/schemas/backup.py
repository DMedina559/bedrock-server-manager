from typing import Optional

from pydantic import BaseModel, Field


class BackupActionPayload(BaseModel):
    """Request model for triggering a backup action."""

    backup_type: str = Field(
        ..., description="Type of backup: 'world', 'config', or 'all'."
    )
    file_to_backup: Optional[str] = Field(
        default=None,
        description="Name of config file if backup_type is 'config' (e.g., 'server.properties').",
    )


class RestoreActionPayload(BaseModel):
    """Request model for triggering a restore action."""

    restore_type: str = Field(
        ...,
        description="Type of restore: 'world', 'properties', 'allowlist', 'permissions', or 'all'.",
    )
    backup_file: Optional[str] = Field(
        default=None,
        description="Name of the backup file (basename) to restore from (required if not 'all').",
    )
