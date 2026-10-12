# bedrock_server_manager/plugins/default/content_uploader_plugin.py
"""
A plugin to provide a web UI for uploading .mcworld, .mcpack, and .mcaddon files.
"""

from pathlib import Path
from typing import Literal
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.contracts import DataContract
from bedrock_server_manager.core.files import atomic_stream_file, validate_archive
from bedrock_server_manager.error import DependencyUnavailableError, UserInputError
from bedrock_server_manager.logging import log_operation_error
from bedrock_server_manager.utils.threads import run_in_thread
from bedrock_server_manager.web import get_admin_user
from bedrock_server_manager.web.schemas import UserResponse

# Define allowed extensions
ALLOWED_EXTENSIONS = {".mcworld", ".mcpack", ".mcaddon"}


def validate_upload(path: Path) -> None:
    try:
        with ZipFile(path) as archive:
            validate_archive(archive)
    except BadZipFile as error:
        raise UserInputError(
            "Upload must contain a valid Minecraft archive."
        ) from error


class UploadResult(DataContract):
    status: Literal["success"] = "success"
    filename: str
    destination: str
    message: str


class ContentUploaderPlugin(PluginBase):
    """Adds a web interface for uploading Minecraft content files (.mcworld, .mcpack, .mcaddon)."""

    version = "2.1.0"
    description = "Adds a web interface for uploading Minecraft content files (.mcworld, .mcpack, .mcaddon)."
    author = "dmedina559"
    name = "Content Uploader"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        self.router = APIRouter(tags=["Content Uploader Plugin"])
        self._define_routes()
        self.logger.debug(
            "ContentUploaderPlugin v%s initialized with routes.", self.version
        )

        result = await self.api.settings.get_global_setting(
            request={"key": "paths.content"}
        )
        if not isinstance(result.value, str) or not result.value:
            raise DependencyUnavailableError("Content directory is not configured.")
        self.content_directory = Path(result.value)
        await run_in_thread(self.content_directory.mkdir, parents=True, exist_ok=True)

    def _define_routes(self):  # noqa: C901
        @self.router.get(
            "/content/upload/ui",
            response_class=JSONResponse,
            name="Content Upload UI",
            summary="Upload Content UI",
            tags=["plugin-json-ui"],
        )
        async def get_upload_json_ui(
            request: Request, current_user: UserResponse = Depends(get_admin_user)
        ):
            return JSONResponse(
                content={
                    "type": "Container",
                    "children": [
                        {
                            "type": "Card",
                            "props": {"title": "Upload Content"},
                            "children": [
                                {
                                    "type": "Text",
                                    "props": {
                                        "content": "Select a .mcworld, .mcpack, or .mcaddon file to upload."
                                    },
                                },
                                {
                                    "type": "FileUpload",
                                    "props": {
                                        "id": "file",
                                        "accept": ".mcworld,.mcpack,.mcaddon",
                                    },
                                },
                                {
                                    "type": "Button",
                                    "props": {
                                        "label": "Upload",
                                        "onClickAction": {
                                            "type": "api_call",
                                            "endpoint": "/api/content/upload",
                                            "includeFormState": True,
                                            "refresh": True,
                                        },
                                    },
                                },
                            ],
                        }
                    ],
                }
            )

        @self.router.post(
            "/api/content/upload",
            name="handle_file_upload",
            response_model=UploadResult,
        )
        async def handle_file_upload_method(
            request: Request,
            file: UploadFile = File(...),
            current_user: UserResponse = Depends(get_admin_user),
        ) -> UploadResult:
            filename = file.filename
            destination: Path | None = None
            completed = False
            primary: BaseException | None = None
            try:
                if not filename:
                    raise UserInputError("Upload filename is required.")
                safe_filename = Path(filename.replace("\\", "/")).name
                extension = Path(safe_filename).suffix.lower()
                if extension not in ALLOWED_EXTENSIONS:
                    raise UserInputError(
                        "Upload must be a .mcworld, .mcpack, or .mcaddon file."
                    )
                directory = "worlds" if extension == ".mcworld" else "addons"
                destination = self.content_directory / directory / safe_filename
                await run_in_thread(
                    atomic_stream_file, file.file, destination, validate=validate_upload
                )
                completed = True
                return UploadResult(
                    filename=safe_filename,
                    destination=str(destination),
                    message=f"Uploaded '{safe_filename}' to {directory}.",
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
                try:
                    await self.api.send_event(
                        "bsm_uploader:upload_processed",
                        filename=filename,
                        destination_path=str(destination) if completed else None,
                        status="success" if completed else "error",
                    )
                except Exception as notification_error:
                    log_operation_error(
                        self.logger,
                        "Could not publish upload notification",
                        error=notification_error,
                    )

    @app_event("on_unload")
    async def plugin_unloaded(self, **kwargs):
        self.logger.debug("Plugin '%s' v%s unloaded.", self.name, self.version)

    def get_fastapi_routers(self, **kwargs):
        self.logger.debug("Providing FastAPI router for %s", self.name)
        return [self.router]
