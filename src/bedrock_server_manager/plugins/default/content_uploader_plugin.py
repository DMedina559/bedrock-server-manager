# bedrock_server_manager/plugins/default/content_uploader_plugin.py
"""
A plugin to provide a web UI for uploading .mcworld, .mcpack, and .mcaddon files.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.web import get_admin_user

from ...logging import log_operation_error

# Define allowed extensions
ALLOWED_EXTENSIONS = {".mcworld", ".mcpack", ".mcaddon"}
MODULE_CONTENT_DIR_PATH: Optional[Path] = None


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

        global MODULE_CONTENT_DIR_PATH

        self.logger.debug(
            "Plugin '%s' v%s loaded. Web uploader available at /content_uploader/page.",
            self.name,
            self.version,
        )

        try:
            setting_result = await self.api.settings.get_global_setting(
                request={"key": "paths.content"}
            )
            if setting_result and setting_result.status == "success":
                path_str = setting_result.value
                if path_str and isinstance(path_str, str):
                    MODULE_CONTENT_DIR_PATH = Path(path_str)
                    self.logger.debug(
                        "Successfully fetched content path. Uploads will be stored relative to: %s",
                        MODULE_CONTENT_DIR_PATH.resolve(),
                    )
                else:
                    self.logger.error(
                        "Content path ('paths.content') from settings is invalid: %s. Using fallback.",
                        path_str,
                    )
                    MODULE_CONTENT_DIR_PATH = None
            else:
                self.logger.error(
                    "Content path unavailable; using the fallback upload directory.",
                )
                MODULE_CONTENT_DIR_PATH = None
        except Exception as e:
            log_operation_error(
                self.logger,
                "Exception fetching 'paths.content': %s. Using fallback.",
                e,
                error=e,
            )
            MODULE_CONTENT_DIR_PATH = None

        if not MODULE_CONTENT_DIR_PATH:
            MODULE_CONTENT_DIR_PATH = Path(os.getcwd()) / "plugin_uploads_fallback"
            self.logger.warning(
                "Using fallback upload directory: %s", MODULE_CONTENT_DIR_PATH.resolve()
            )

        try:
            MODULE_CONTENT_DIR_PATH.mkdir(parents=True, exist_ok=True)
            self.logger.debug(
                "Ensured base upload directory exists: %s",
                MODULE_CONTENT_DIR_PATH.resolve(),
            )
        except Exception as e:
            log_operation_error(
                self.logger,
                "Could not create/verify base upload directory %s: %s",
                MODULE_CONTENT_DIR_PATH.resolve(),
                e,
                error=e,
            )

    def _define_routes(self):  # noqa: C901
        @self.router.get(
            "/content/upload/ui",
            response_class=JSONResponse,
            name="Content Upload UI",
            summary="Upload Content UI",
            tags=["plugin-json-ui"],
        )
        async def get_upload_json_ui(
            request: Request, current_user: Dict[str, Any] = Depends(get_admin_user)
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

        @self.router.post("/api/content/upload", name="handle_file_upload")
        async def handle_file_upload_method(
            request: Request,
            file: UploadFile = File(...),
            current_user: Dict[str, Any] = Depends(get_admin_user),
        ):
            filename = file.filename
            file_content_type = file.content_type

            if self.api:
                await self.api.send_event(
                    "bsm_uploader:upload_initiated",
                    filename=filename,
                    content_type=file_content_type,
                )

            message = ""
            destination_path_for_event: Optional[str] = None
            event_status = "error"

            try:
                if not MODULE_CONTENT_DIR_PATH:
                    self.logger.error(
                        "Base content directory path is not set. Cannot process upload."
                    )
                    message = (
                        "Upload failed: Server content directory is not configured."
                    )
                    raise ValueError("MODULE_CONTENT_DIR_PATH not set")

                if not filename:
                    raise ValueError("Filename is missing")

                file_ext = Path(filename).suffix.lower()
                target_subdir_name = ""

                if file_ext == ".mcworld":
                    target_subdir_name = "worlds"
                elif file_ext in [".mcpack", ".mcaddon"]:
                    target_subdir_name = "addons"

                if not target_subdir_name:
                    self.logger.warning(
                        "Upload failed: File '%s' has an invalid or unsupported extension '%s'.",
                        filename,
                        file_ext,
                    )
                    message = f"Upload failed: File type '{file_ext}' is not allowed or unsupported."
                else:
                    target_base_dir = MODULE_CONTENT_DIR_PATH / target_subdir_name
                    target_base_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.debug(
                        "Ensured target upload subdirectory exists: %s",
                        target_base_dir.resolve(),
                    )

                    safe_filename = Path(filename).name
                    destination_path = target_base_dir / safe_filename
                    destination_path_for_event = str(destination_path.resolve())

                    self.logger.debug(
                        "Attempting to save uploaded file '%s' to '%s'.",
                        filename,
                        destination_path,
                    )
                    with open(destination_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)

                    self.logger.info(
                        "File '%s' saved successfully to '%s'.",
                        filename,
                        destination_path,
                    )
                    message = f"File '{safe_filename}' uploaded successfully to: {target_subdir_name}/{safe_filename}"
                    event_status = "success"

            except Exception as e:
                log_operation_error(
                    self.logger,
                    "Error during file upload or processing for '%s': %s",
                    filename,
                    e,
                    error=e,
                )
                message = (
                    "An unexpected error occurred while processing the file upload."
                )
                event_status = "error"
            finally:
                if hasattr(file, "file") and file.file:
                    file.file.close()

                if self.api:
                    await self.api.send_event(
                        "bsm_uploader:upload_processed",
                        filename=filename,
                        destination_path=destination_path_for_event,
                        status=event_status,
                        details_message=message,
                    )

            return JSONResponse(
                content={
                    "status": event_status,
                    "message": message,
                    "destination": destination_path_for_event,
                },
                status_code=200 if event_status == "success" else 400,
            )

    @app_event("on_unload")
    async def plugin_unloaded(self, **kwargs):
        self.logger.debug("Plugin '%s' v%s unloaded.", self.name, self.version)

    def get_fastapi_routers(self, **kwargs):
        self.logger.debug("Providing FastAPI router for %s", self.name)
        return [self.router]
