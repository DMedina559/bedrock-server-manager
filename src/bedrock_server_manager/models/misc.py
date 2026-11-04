"""Serializable misc API and HTTP contracts."""

from typing import Annotated

from pydantic import Field

from .common import ActionResponse, APIRequest, CleanupResult, NonEmptyStr


class PruneDownloadsPayload(APIRequest):
    """Request model for pruning the download cache."""

    directory: NonEmptyStr = Field(
        ...,
        description="The subdirectory within the main download cache to prune (e.g., 'stable' or 'preview').",
    )
    keep: int | None = Field(
        default=None,
        ge=0,
        description="Number of most recent files to keep. Defaults to config if omitted.",
    )


class PruneDownloadCacheRequest(APIRequest):
    download_dir: NonEmptyStr
    keep_count: Annotated[int, Field(ge=0)] | None = None


class PruneDownloadCacheResponse(ActionResponse):
    result: CleanupResult = Field(default_factory=CleanupResult)
