from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import ConfigDict, Field, JsonValue

from ...api.models.common import APIRequest, APIResponse, SuccessResponse
from ...contracts import FailureInfo, NonEmptyStr
from .base import BaseApiResponse

ContentCategory = Literal["worlds", "addons"]


class ContentUploadResponse(SuccessResponse):
    """Response model for uploading a world or addon archive to the content library."""

    filename: str
    category: ContentCategory
    destination: str


class SetupStatusResponse(APIResponse):
    """Response model for setup status."""

    needs_setup: bool


class FileNamePayload(APIRequest):
    """Payload for file-based operations.

    :ivar filename: The name of the file to operate on.
    """

    filename: NonEmptyStr


class SettingItemPayload(APIRequest):
    """Request model for a single setting key-value pair."""

    key: NonEmptyStr = Field(
        ..., description="The dot-notation key of the setting (e.g., 'web.port')."
    )
    value: JsonValue = Field(..., description="The new value for the setting.")


class SettingsResponse(BaseApiResponse):
    """Response model for settings operations."""

    settings: Optional[Dict[str, JsonValue]] = None
    setting: Optional[SettingItemPayload] = None


class PruneDownloadsPayload(APIRequest):
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


class AuditLogResponse(APIResponse):
    id: int
    user_id: int
    action: str
    details: Optional[Dict[str, JsonValue]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class PruneDownloadsResponse(BaseApiResponse):
    """Response model for pruning downloads."""

    failures: dict[str, FailureInfo] = Field(default_factory=dict)
    files_deleted: Optional[int] = None
    files_kept: Optional[int] = None


class ThemeListResponse(BaseApiResponse):
    """Response model for theme lists."""

    themes: Optional[List[str]] = None
