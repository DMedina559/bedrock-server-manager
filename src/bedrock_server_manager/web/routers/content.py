"""FastAPI router for uploading, downloading, and deleting content templates (.mcworld, .mcpack, .mcaddon)."""

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Literal
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, HTTPException, Security, UploadFile
from fastapi.responses import FileResponse

from bedrock_server_manager.api.models import (
    ListAvailableAddonsRequest,
    ListAvailableWorldsRequest,
)

from ...api import addon as addon_api
from ...api import application as app_api
from ...context import AppContext
from ...contracts import DataContract
from ...core.files import atomic_stream_file, validate_archive
from ...error import DependencyUnavailableError, UserInputError
from ...logging import log_operation_error
from ...utils.threads import run_in_thread
from ..access_policy import Permission
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import BaseApiResponse, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Content Management"])

ALLOWED_EXTENSIONS = {".mcworld", ".mcpack", ".mcaddon"}
SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._\- ]+$")
ContentCategory = Literal["worlds", "addons"]


def validate_upload(path: Path) -> None:
    """Validate that an uploaded content file is a safe ZIP archive."""
    try:
        with ZipFile(path) as archive:
            validate_archive(archive)
    except BadZipFile as error:
        raise UserInputError(
            "Upload must contain a valid Minecraft archive."
        ) from error


class ContentUploadResponse(DataContract):
    status: Literal["success"] = "success"
    filename: str
    category: ContentCategory
    destination: str
    message: str


async def _resolve_content_file(
    app_context: AppContext,
    category: ContentCategory,
    filename: str,
) -> Path:
    if not filename or len(filename) > 255 or not SAFE_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if category == "worlds":
        listing_files = (
            await app_api.list_available_worlds(
                request=ListAvailableWorldsRequest(), app_context=app_context
            )
        ).files
    elif category == "addons":
        listing_files = (
            await addon_api.list_available_addons(
                request=ListAvailableAddonsRequest(), app_context=app_context
            )
        ).files
    else:
        raise HTTPException(status_code=400, detail="Invalid content category.")

    matched = next(
        (Path(path) for path in listing_files if os.path.basename(path) == filename),
        None,
    )
    if matched is None:
        raise HTTPException(status_code=404, detail="Content file not found.")

    base_path = await asyncio.to_thread(matched.parent.resolve)

    def _check_path() -> Path:
        if not base_path.exists():
            raise HTTPException(status_code=404, detail="Content directory not found.")
        candidate = base_path / filename
        if candidate.is_symlink():
            raise HTTPException(status_code=403, detail="File links are not supported.")
        resolved_file = candidate.resolve()
        try:
            resolved_file.relative_to(base_path)
        except ValueError as err:
            raise HTTPException(
                status_code=403, detail="Access denied: Path traversal detected."
            ) from err
        if not resolved_file.exists() or not resolved_file.is_file():
            raise HTTPException(status_code=404, detail="Content file not found.")
        return resolved_file

    return await asyncio.to_thread(_check_path)


@router.post(
    "/api/content/upload",
    operation_id="upload_content_file",
    response_model=ContentUploadResponse,
)
async def upload_content_file(
    file: UploadFile = File(..., json_schema_extra={"format": "binary"}),
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.CONTENT_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> ContentUploadResponse:
    """Upload a ``.mcworld``, ``.mcpack``, or ``.mcaddon`` template file to the content library."""
    filename = file.filename
    destination: Path | None = None
    primary: BaseException | None = None
    try:
        if not filename:
            raise UserInputError("Upload filename is required.")
        safe_filename = Path(filename.replace("\\", "/")).name
        if not SAFE_FILENAME_PATTERN.match(safe_filename):
            raise UserInputError("Upload filename contains unsupported characters.")
        extension = Path(safe_filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise UserInputError(
                "Upload must be a .mcworld, .mcpack, or .mcaddon file."
            )
        category: ContentCategory = "worlds" if extension == ".mcworld" else "addons"
        content_dir_val = app_context.settings.get("paths.content")
        if not isinstance(content_dir_val, str) or not content_dir_val:
            raise DependencyUnavailableError("Content directory is not configured.")
        destination = Path(content_dir_val) / category / safe_filename
        await run_in_thread(
            atomic_stream_file, file.file, destination, validate=validate_upload
        )
        return ContentUploadResponse(
            filename=safe_filename,
            category=category,
            destination=str(destination),
            message=f"Uploaded '{safe_filename}' to {category}.",
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            await file.close()
        except Exception as cleanup_error:
            if primary is None:
                raise
            primary.add_note(
                f"Upload close also failed: {type(cleanup_error).__name__}"
            )


@router.get(
    "/api/content/{category}/{filename}/download",
    operation_id="download_content_file",
    response_class=FileResponse,
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
async def download_content_file(
    category: ContentCategory,
    filename: str,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.CONTENT_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> FileResponse:
    """Download a world or addon archive from the content library."""
    try:
        file_path = await _resolve_content_file(app_context, category, filename)
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-store"},
        )
    except HTTPException:
        raise
    except Exception as error:
        log_operation_error(logger, "Content download error: %s", error, error=error)
        raise HTTPException(
            status_code=500, detail="Internal server error during content download."
        ) from error


@router.delete(
    "/api/content/{category}/{filename}",
    operation_id="delete_content_file",
    response_model=BaseApiResponse,
)
async def delete_content_file(
    category: ContentCategory,
    filename: str,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.CONTENT_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    """Delete a world or addon archive from the content library."""
    file_path = await _resolve_content_file(app_context, category, filename)
    try:
        await asyncio.to_thread(file_path.unlink)
    except OSError as error:
        log_operation_error(logger, "Content delete error: %s", error, error=error)
        raise HTTPException(
            status_code=500, detail="Could not delete content file."
        ) from error
    return BaseApiResponse(
        status="success",
        message=f"Deleted '{filename}' from {category}.",
    )
