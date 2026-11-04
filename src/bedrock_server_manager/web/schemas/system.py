from datetime import datetime
from typing import Dict, List, Optional

from pydantic import ConfigDict, JsonValue

from ...models.common import APIResponse, ContentCategory, SuccessResponse
from ...models.misc import PruneDownloadsPayload
from ...models.settings import SettingItemPayload
from ...models.system import FileNamePayload
from .base import BaseApiResponse


class ContentUploadResponse(SuccessResponse):
    """Response model for uploading a world or addon archive to the content library."""

    filename: str
    category: ContentCategory
    destination: str


class SetupStatusResponse(APIResponse):
    """Response model for setup status."""

    needs_setup: bool


class AuditLogResponse(APIResponse):
    id: int
    user_id: int
    action: str
    details: Optional[Dict[str, JsonValue]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class ThemeListResponse(BaseApiResponse):
    """Response model for theme lists."""

    themes: Optional[List[str]] = None


__all__ = [
    "AuditLogResponse",
    "ContentCategory",
    "ContentUploadResponse",
    "FileNamePayload",
    "PruneDownloadsPayload",
    "SettingItemPayload",
    "SetupStatusResponse",
    "ThemeListResponse",
]
