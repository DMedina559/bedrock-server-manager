import asyncio
import os
import re
from pathlib import Path
from typing import Annotated, Any, List, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.error import InvalidServerNameError
from bedrock_server_manager.logging import log_operation_error
from bedrock_server_manager.utils.server import core_validate_server_name_format
from bedrock_server_manager.web import get_admin_user
from bedrock_server_manager.web.schemas import UserResponse


class DownloadPageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server: str | None = None
    type: Literal["backups", "content"] = "backups"


class DownloadFileQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_type: Literal[
        "backup_snapshot",
        "backup_world",
        "backup_config",
        "content_world",
        "content_addon",
    ]
    filename: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._\- ]+$")
    server: str | None = None


class DownloadPagePlugin(PluginBase):
    """Adds a download page to the web interface for server backups and content."""

    version = "1.2.0"
    description = (
        "Adds a download page to the web interface for server backups and content."
    )
    author = "dmedina559"
    name = "Download Page"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        self.router = APIRouter(tags=["Download Page Plugin"])
        self._define_routes()
        self.logger.debug("Plugin '%s' v%s initialized.", self.name, self.version)

    def _define_routes(self):  # noqa: C901
        @self.router.get(
            "/api/download_page/ui",
            response_class=JSONResponse,
            operation_id="download_page_ui",
            name="Download Page UI",
            summary="Download Page UI",
            tags=["plugin-json-ui"],
        )
        async def get_download_page_ui(
            query: Annotated[DownloadPageQuery, Query()],
            current_user: UserResponse = Depends(get_admin_user),
        ):
            server = query.server
            type = query.type
            if not server:
                return JSONResponse(
                    content={
                        "type": "Container",
                        "children": [
                            {
                                "type": "Card",
                                "props": {"title": "Select Server"},
                                "children": [
                                    {
                                        "type": "Text",
                                        "props": {
                                            "content": "Please select a server from the sidebar to view downloads.",
                                            "variant": "body",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                )

            # Dropdown options
            type_options = [
                {"label": "Backups", "value": "backups"},
                {"label": "Content", "value": "content"},
            ]

            tabs_children: list[dict[str, Any]] = []

            if type == "backups":
                # Fetch Backups
                world_backups = []
                properties_backups = []
                allowlist_backups = []
                permissions_backups = []

                try:

                    file_list = await self.api.backup_restore.list_backup_files(
                        request={"server_name": server, "backup_type": "all"}
                    )

                    if not isinstance(file_list.backups, dict):
                        raise ValueError("Expected grouped backup files")
                    # World Backups
                    wb_res = file_list.backups.get("world_backups", [])
                    if file_list.status == "success":
                        world_backups = [os.path.basename(p) for p in wb_res]

                    # Properties Backups
                    pb_res = file_list.backups.get("properties_backups", [])
                    if file_list.status == "success":
                        properties_backups = [os.path.basename(p) for p in pb_res]

                    # Allowlist Backups
                    ab_res = file_list.backups.get("allowlist_backups", [])
                    if file_list.status == "success":
                        allowlist_backups = [os.path.basename(p) for p in ab_res]

                    # Permissions Backups
                    prm_res = file_list.backups.get("permissions_backups", [])
                    if file_list.status == "success":
                        permissions_backups = [os.path.basename(p) for p in prm_res]

                except Exception as e:
                    log_operation_error(
                        self.logger, "Error listing backups: %s", e, error=e
                    )
                    raise

                snapshots = await self.api.backup_restore.list_server_snapshots(
                    request={"server_name": server}
                )
                tabs_children = [
                    {
                        "type": "Tab",
                        "props": {"id": "snapshots", "label": "Server backups"},
                        "children": [
                            self._create_file_list_table(
                                [item.filename for item in snapshots.backups],
                                "backup_snapshot",
                                server,
                            )
                        ],
                    },
                    {
                        "type": "Tab",
                        "props": {"id": "world_backups", "label": "Worlds"},
                        "children": [
                            self._create_file_list_table(
                                world_backups, "backup_world", server
                            )
                        ],
                    },
                    {
                        "type": "Tab",
                        "props": {"id": "properties_backups", "label": "Properties"},
                        "children": [
                            self._create_file_list_table(
                                properties_backups, "backup_config", server
                            )
                        ],
                    },
                    {
                        "type": "Tab",
                        "props": {"id": "allowlist_backups", "label": "Allowlist"},
                        "children": [
                            self._create_file_list_table(
                                allowlist_backups, "backup_config", server
                            )
                        ],
                    },
                    {
                        "type": "Tab",
                        "props": {"id": "permissions_backups", "label": "Permissions"},
                        "children": [
                            self._create_file_list_table(
                                permissions_backups, "backup_config", server
                            )
                        ],
                    },
                ]

            elif type == "content":
                # Fetch Content
                worlds = []
                addons = []
                try:

                    worlds_list = await self.api.application.list_available_worlds(
                        request={}
                    )
                    addons_list = await self.api.addon.list_available_addons(request={})

                    if worlds_list.status == "success":
                        worlds = [os.path.basename(p) for p in worlds_list.files]

                    if addons_list.status == "success":
                        addons = [os.path.basename(p) for p in addons_list.files]

                except Exception as e:
                    log_operation_error(
                        self.logger, "Error listing content: %s", e, error=e
                    )
                    raise

                tabs_children = [
                    {
                        "type": "Tab",
                        "props": {"id": "worlds", "label": "Worlds"},
                        "children": [
                            self._create_file_list_table(
                                worlds, "content_world", server
                            )
                        ],
                    },
                    {
                        "type": "Tab",
                        "props": {"id": "addons", "label": "Addons"},
                        "children": [
                            self._create_file_list_table(
                                addons, "content_addon", server
                            )
                        ],
                    },
                ]

            return JSONResponse(
                content={
                    "type": "Container",
                    "children": [
                        {
                            "type": "Card",
                            "props": {"title": f"Downloads for {server}"},
                            "children": [
                                {
                                    "type": "Row",
                                    "children": [
                                        {
                                            "type": "Select",
                                            "props": {
                                                "id": "download_type",
                                                "value": type,
                                                "options": type_options,
                                                "onChangeAction": {
                                                    "type": "navigate",
                                                    "dynamicParam": "type",  # The frontend will set 'type' param to the new value
                                                    "params": {
                                                        "server": server
                                                    },  # Ensure server param is kept
                                                },
                                            },
                                        }
                                    ],
                                },
                                {
                                    "type": "Tabs",
                                    "props": {
                                        "activeTab": (
                                            list(tabs_children)[0]["props"]["id"]
                                            if tabs_children
                                            and isinstance(list(tabs_children)[0], dict)
                                            and "props" in list(tabs_children)[0]
                                            else ""
                                        )
                                    },  # default to first tab
                                    "children": tabs_children,
                                },
                            ],
                        }
                    ],
                }
            )

        @self.router.get(
            "/api/download_page/download", operation_id="download_page_file"
        )
        async def download_file(
            query: Annotated[DownloadFileQuery, Query()],
            request: Request,
            current_user: UserResponse = Depends(get_admin_user),
        ):
            file_type = query.file_type
            filename = query.filename
            server = query.server
            # Strict validation of user-controlled inputs to avoid path traversal
            # Allow alphanumeric, dot, underscore, dash, and space
            safe_name_pattern = re.compile(r"^[A-Za-z0-9._\- ]+$")
            if not safe_name_pattern.match(filename):
                raise HTTPException(400, "Invalid filename")

            if server is not None:
                try:
                    core_validate_server_name_format(server)
                except InvalidServerNameError as e:
                    raise HTTPException(400, f"Invalid server name: {e}")

            base_path = None
            # Resolve root directories first to establish trust anchors
            if file_type in ("backup_snapshot", "backup_world", "backup_config"):
                if not server:
                    raise HTTPException(400, "Server name required for backups")
                if file_type == "backup_snapshot":
                    snapshot_listing = (
                        await self.api.backup_restore.list_server_snapshots(
                            request={"server_name": server}
                        )
                    )
                    if filename not in {
                        item.filename for item in snapshot_listing.backups
                    }:
                        raise HTTPException(404, "Backup archive not found")
                    prefix = request.scope.get("root_path", "").rstrip("/")
                    return RedirectResponse(
                        f"{prefix}/api/server/{quote(server, safe='')}/backups/{quote(filename, safe='')}/download",
                        status_code=307,
                    )
                legacy_listing = await self.api.backup_restore.list_backup_files(
                    request={
                        "server_name": server,
                        "backup_type": (
                            "world" if file_type == "backup_world" else "all"
                        ),
                    }
                )
                grouped = legacy_listing.backups
                allowed = (
                    grouped
                    if isinstance(grouped, list)
                    else [
                        path
                        for name, paths in grouped.items()
                        if name != "world_backups"
                        for path in paths
                    ]
                )
                if filename not in {os.path.basename(path) for path in allowed}:
                    raise HTTPException(404, "Legacy backup file not found")
                result = await self.api.settings.get_global_setting(
                    request={"key": "paths.backups"}
                )
                backup_dir_str = result.value if result.status == "success" else None
                if not isinstance(backup_dir_str, str) or not backup_dir_str:
                    raise HTTPException(500, "Backup directory not configured")

                def _resolve_backup_base() -> Path:
                    backup_root = Path(backup_dir_str).resolve()
                    if not backup_root.exists():
                        raise HTTPException(500, "Backup root directory does not exist")
                    assert server is not None
                    resolved_base = (backup_root / server).resolve()
                    try:
                        resolved_base.relative_to(backup_root)
                    except ValueError:
                        raise HTTPException(403, "Access denied: Invalid server path")
                    return resolved_base

                base_path = await asyncio.to_thread(_resolve_backup_base)

            elif file_type in ("content_world", "content_addon"):
                result = await self.api.settings.get_global_setting(
                    request={"key": "paths.content"}
                )
                content_dir_str = result.value if result.status == "success" else None
                if not isinstance(content_dir_str, str) or not content_dir_str:
                    raise HTTPException(500, "Content directory not configured")

                def _resolve_content_base() -> Path:
                    content_root = Path(content_dir_str).resolve()
                    if not content_root.exists():
                        raise HTTPException(
                            500, "Content root directory does not exist"
                        )
                    if file_type == "content_world":
                        resolved_base = (content_root / "worlds").resolve()
                    else:
                        resolved_base = (content_root / "addons").resolve()
                    try:
                        resolved_base.relative_to(content_root)
                    except ValueError:
                        raise HTTPException(
                            500, "Content subdirectory is outside content root"
                        )
                    return resolved_base

                base_path = await asyncio.to_thread(_resolve_content_base)
            else:
                raise HTTPException(400, "Invalid file type")

            def _resolve_file_path() -> Path:
                if not base_path.exists():
                    raise HTTPException(
                        404, "Base directory not found or does not exist"
                    )
                if (base_path / filename).is_symlink():
                    raise HTTPException(403, "File links are not supported")
                resolved_file = (base_path / filename).resolve()
                try:
                    resolved_file.relative_to(base_path)
                except ValueError:
                    raise HTTPException(403, "Access denied: Path traversal detected")
                if not resolved_file.exists() or not resolved_file.is_file():
                    raise HTTPException(404, "File not found")
                return resolved_file

            # Secure path joining
            try:
                file_path = await asyncio.to_thread(_resolve_file_path)
                return FileResponse(path=file_path, filename=filename)
            except HTTPException:
                # Re-raise HTTPExceptions as-is
                raise
            except Exception as e:
                log_operation_error(self.logger, "Download error: %s", e, error=e)
                raise HTTPException(500, "Internal server error during download")

    def _create_file_list_table(
        self,
        files: List[str],
        file_type: Literal[
            "backup_snapshot",
            "backup_world",
            "backup_config",
            "content_world",
            "content_addon",
        ],
        server: Optional[str],
    ) -> dict:
        if not files:
            return {
                "type": "Text",
                "props": {
                    "content": "No files found.",
                    "variant": "body",
                    "style": {"fontStyle": "italic", "color": "#888"},
                },
            }

        # Build rows for the Table component
        # Each row is an array of cells. Cells can be strings or components.
        rows = []
        for f in files:
            rows.append(
                [
                    f,  # Filename column
                    {
                        "type": "FileDownload",
                        "props": {
                            "label": "Download",
                            "endpoint": (
                                f"/api/server/{quote(server or '', safe='')}/backups/{quote(f, safe='')}/download"
                                if file_type == "backup_snapshot"
                                else f"/api/download_page/download?file_type={file_type}&filename={quote(f, safe='')}&server={quote(server or '', safe='')}"
                            ),
                            "filename": f,
                            "style": {
                                "marginLeft": "auto"
                            },  # Push button to right if in flex, or just add spacing
                        },
                    },
                ]
            )

        return {
            "type": "Table",
            "props": {
                "headers": ["Filename", "Action"],
                "rows": rows,
                "style": {"width": "100%"},  # Ensure table uses full width
            },
        }

    @app_event("on_unload")
    async def plugin_unloaded(self, **kwargs):
        self.logger.debug("Plugin '%s' v%s unloaded.", self.name, self.version)

    def get_fastapi_routers(self, **kwargs):
        return [self.router]
