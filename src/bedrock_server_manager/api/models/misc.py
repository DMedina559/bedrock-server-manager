"""Serializable misc API request and response contracts."""

from typing import Annotated

from pydantic import Field

from ...results import CleanupResult
from .common import ActionResponse, APIRequest, NonEmptyStr


class PruneDownloadCacheRequest(APIRequest):
    download_dir: NonEmptyStr
    keep_count: Annotated[int, Field(ge=0)] | None = None


class PruneDownloadCacheResponse(ActionResponse):
    result: CleanupResult = Field(default_factory=CleanupResult)
