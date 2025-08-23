# bedrock_server_manager/plugins/default/content_uploader/__init__.py
"""
A plugin to provide a web UI for uploading .mcworld, .mcpack, and .mcaddon files.
"""
import os
import shutil
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Request, File, UploadFile, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from bedrock_server_manager import PluginBase
from bedrock_server_manager.web import get_admin_user

# Define allowed extensions
ALLOWED_EXTENSIONS = {".mcworld", ".mcpack", ".mcaddon"}
MODULE_CONTENT_DIR_PATH: Optional[Path] = None


class ContentUploaderPlugin(PluginBase):
    version = "1.1.0"

    def on_load(self, **kwargs):
        self.router = APIRouter(tags=["Content Uploader Plugin"])
        self._define_routes()
        self.logger.info(
            f"ContentUploaderPlugin v{self.version} initialized with routes."
        )

        global MODULE_CONTENT_DIR_PATH

        self.logger.info(
            f"Plugin '{self.name}' v{self.version} loaded. Web uploader available at /content_uploader/page."
        )

        try:
            setting_result = self.api.get_global_setting(key="paths.content")
            if setting_result and setting_result.get("status") == "success":
                path_str = setting_result.get("value")
                if path_str and isinstance(path_str, str):
                    MODULE_CONTENT_DIR_PATH = Path(path_str)
                    self.logger.info(
                        f"Successfully fetched content path. Uploads will be stored relative to: {MODULE_CONTENT_DIR_PATH.resolve()}"
                    )
                else:
                    self.logger.error(
                        f"Content path ('paths.content') from settings is invalid: {path_str}. Using fallback."
                    )
                    MODULE_CONTENT_DIR_PATH = None
            else:
                self.logger.error(
                    f"Failed to get 'paths.content'. API response: {setting_result}. Using fallback."
                )
                MODULE_CONTENT_DIR_PATH = None
        except Exception as e:
            self.logger.error(
                f"Exception fetching 'paths.content': {e}. Using fallback.",
                exc_info=True,
            )
            MODULE_CONTENT_DIR_PATH = None

        if not MODULE_CONTENT_DIR_PATH:
            MODULE_CONTENT_DIR_PATH = Path(os.getcwd()) / "plugin_uploads_fallback"
            self.logger.warning(
                f"Using fallback upload directory: {MODULE_CONTENT_DIR_PATH.resolve()}"
            )

        try:
            MODULE_CONTENT_DIR_PATH.mkdir(parents=True, exist_ok=True)
            self.logger.info(
                f"Ensured base upload directory exists: {MODULE_CONTENT_DIR_PATH.resolve()}"
            )
        except Exception as e:
            self.logger.error(
                f"Could not create/verify base upload directory {MODULE_CONTENT_DIR_PATH.resolve()}: {e}",
                exc_info=True,
            )

    def _define_routes(self):
        @self.router.get(
            "/content/upload",
            response_class=HTMLResponse,
            name="Content Upload Page",
            summary="Upload Content",
            tags=["plugin-ui"],
        )
        async def get_upload_page_method(
            request: Request,
            current_user: Dict[str, Any] = Depends(get_admin_user),
        ):
            self.logger.debug("Serving content upload page using TemplateResponse.")

            templates_env = self.api.app_context.templates
            return templates_env.TemplateResponse(
                "upload_page.html", {"request": request}
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
                self.api.send_event(
                    "bsm_uploader:upload_initiated",
                    filename=filename,
                    content_type=file_content_type,
                )

            message = ""
            message_type = "info"
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
                    message_type = "error"
                    raise ValueError("MODULE_CONTENT_DIR_PATH not set")

                file_ext = Path(filename).suffix.lower()
                target_subdir_name = ""

                if file_ext == ".mcworld":
                    target_subdir_name = "worlds"
                elif file_ext in [".mcpack", ".mcaddon"]:
                    target_subdir_name = "addons"

                if not target_subdir_name:
                    self.logger.warning(
                        f"Upload failed: File '{filename}' has an invalid or unsupported extension '{file_ext}'."
                    )
                    message = f"Upload failed: File type '{file_ext}' is not allowed or unsupported."
                    message_type = "error"
                else:
                    target_base_dir = MODULE_CONTENT_DIR_PATH / target_subdir_name
                    target_base_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.info(
                        f"Ensured target upload subdirectory exists: {target_base_dir.resolve()}"
                    )

                    safe_filename = Path(filename).name
                    destination_path = target_base_dir / safe_filename
                    destination_path_for_event = str(destination_path.resolve())

                    self.logger.info(
                        f"Attempting to save uploaded file '{filename}' to '{destination_path}'."
                    )
                    with open(destination_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)

                    self.logger.info(
                        f"File '{filename}' saved successfully to '{destination_path}'."
                    )
                    message = f"File '{safe_filename}' uploaded successfully to: {target_subdir_name}/{safe_filename}"
                    message_type = "success"
                    event_status = "success"

                    if file_ext == ".mcworld":
                        self.logger.info(
                            f'Placeholder: Post-upload, would call self.api.import_world(server_name, "{destination_path}")'
                        )
                    elif file_ext in [".mcpack", ".mcaddon"]:
                        self.logger.info(
                            f'Placeholder: Post-upload, would call self.api.import_addon(server_name, "{destination_path}")'
                        )

            except Exception as e:
                self.logger.error(
                    f"Error during file upload or processing for '{filename}': {e}",
                    exc_info=True,
                )
                message = f"An unexpected error occurred: {str(e)}"
                message_type = "error"
                event_status = "error"
            finally:
                if hasattr(file, "file") and file.file:
                    file.file.close()

                if self.api:
                    self.api.send_event(
                        "bsm_uploader:upload_processed",
                        filename=filename,
                        destination_path=destination_path_for_event,
                        status=event_status,
                        details_message=message,
                    )

            redirect_url = request.url_for("Content Upload Page").include_query_params(
                message=message, message_type=message_type
            )
            return RedirectResponse(url=str(redirect_url), status_code=303)

    def on_unload(self, **kwargs):
        self.logger.info(f"Plugin '{self.name}' v{self.version} unloaded.")

    def get_fastapi_routers(self, **kwargs):
        self.logger.debug(f"Providing FastAPI router for {self.name}")
        return [self.router]

    def get_template_paths(self, **kwargs) -> list[Path]:
        plugin_dir = Path(__file__).parent
        return [plugin_dir / "templates"]
