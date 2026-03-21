from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .base import BaseApiResponse


class FileNamePayload(BaseModel):
    """
    Payload for file-based operations.

    Attributes:
        filename (str): The name of the file to operate on.
    """

    filename: str


class SettingItem(BaseModel):
    """Request model for a single setting key-value pair."""

    key: str = Field(
        ..., description="The dot-notation key of the setting (e.g., 'web.port')."
    )
    value: Any = Field(..., description="The new value for the setting.")


class SettingsResponse(BaseApiResponse):
    """Response model for settings operations."""

    # status: str = Field(...) -> Inherited
    # message: Optional[str] = None -> Inherited
    settings: Optional[Dict[str, Any]] = None
    setting: Optional[SettingItem] = None


class PruneDownloadsPayload(BaseModel):
    """Request model for pruning the download cache."""

    directory: str = Field(
        ...,
        min_length=1,
        description="The subdirectory within the main download cache to prune (e.g., 'stable' or 'preview').",
    )
    keep: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of most recent files to keep. Defaults to config if omitted.",
    )


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class PruneDownloadsResponse(BaseApiResponse):
    """Response model for pruning downloads."""

    files_deleted: Optional[int] = None
    files_kept: Optional[int] = None


class ContentListResponse(BaseApiResponse):
    """
    Response model for content listing endpoints.

    Attributes:
        files (Optional[List[str]]): A list of filenames found.
    """

    # status: str -> Inherited
    # message: Optional[str] = None -> Inherited
    files: Optional[List[str]] = None
