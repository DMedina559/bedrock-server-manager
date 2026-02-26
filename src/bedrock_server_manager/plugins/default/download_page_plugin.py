import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from bedrock_server_manager import PluginBase
from bedrock_server_manager.web import get_admin_user


class DownloadPagePlugin(PluginBase):
    """Adds a download page to the web interface for server backups and content."""

    version = "1.0.0"
    author = "dmedina559"

    def on_load(self, **kwargs):
        self.router = APIRouter(tags=["Download Page Plugin"])
        self._define_routes()
        self.logger.info(f"Plugin '{self.name}' v{self.version} initialized.")

    def _define_routes(self):  # noqa: C901
        @self.router.get(
            "/api/download_page/ui",
            response_class=JSONResponse,
            name="Download Page UI",
            summary="Download Page UI",
            tags=["plugin-ui-native"],
        )
        async def get_download_page_ui(
            server: Optional[str] = Query(None),
            type: str = Query("backups"),
            current_user: Dict[str, Any] = Depends(get_admin_user),
        ):
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

            tabs_children = []

            if type == "backups":
                # Fetch Backups
                world_backups = []
                properties_backups = []
                allowlist_backups = []
                permissions_backups = []

                try:

                    file_list = self.api.list_backup_files(
                        server_name=server, backup_type="all"
                    )

                    # World Backups
                    wb_res = file_list["backups"]["world_backups"]
                    if file_list["status"] == "success":
                        world_backups = [os.path.basename(p) for p in wb_res]

                    # Properties Backups
                    pb_res = file_list["backups"]["properties_backups"]
                    if file_list["status"] == "success":
                        properties_backups = [os.path.basename(p) for p in pb_res]

                    # Allowlist Backups
                    ab_res = file_list["backups"]["allowlist_backups"]
                    if file_list["status"] == "success":
                        allowlist_backups = [os.path.basename(p) for p in ab_res]

                    # Permissions Backups
                    prm_res = file_list["backups"]["permissions_backups"]
                    if file_list["status"] == "success":
                        permissions_backups = [os.path.basename(p) for p in prm_res]

                except Exception as e:
                    self.logger.error(f"Error listing backups: {e}")

                tabs_children = [
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

                    worlds_list = self.api.list_available_worlds_api()
                    addons_list = self.api.list_available_addons_api()

                    if worlds_list["status"] == "success":
                        worlds = [
                            os.path.basename(p) for p in worlds_list.get("files", [])
                        ]

                    if addons_list["status"] == "success":
                        addons = [
                            os.path.basename(p) for p in addons_list.get("files", [])
                        ]

                except Exception as e:
                    self.logger.error(f"Error listing content: {e}")

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
                                            tabs_children[0]["props"]["id"]
                                            if tabs_children
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

        @self.router.get("/api/download_page/download")
        async def download_file(
            file_type: str,
            filename: str,
            server: Optional[str] = None,
            current_user: Dict[str, Any] = Depends(get_admin_user),
        ):
            # Strict validation of user-controlled inputs to avoid path traversal
            # Allow alphanumeric, dot, underscore, dash, and space
            safe_name_pattern = re.compile(r"^[A-Za-z0-9._\- ]+$")
            if not safe_name_pattern.match(filename):
                raise HTTPException(400, "Invalid filename")

            if server is not None:
                if not safe_name_pattern.match(server):
                    raise HTTPException(400, "Invalid server name")

            base_path = None
            # Resolve root directories first to establish trust anchors
            if file_type in ("backup_world", "backup_config"):
                if not server:
                    raise HTTPException(400, "Server name required for backups")
                backup_dir_str = self.api.app_context.settings.get("paths.backups")
                if not backup_dir_str:
                    raise HTTPException(500, "Backup directory not configured")

                # Trust anchor for backups
                backup_root = Path(backup_dir_str).resolve()
                if not backup_root.exists():
                    raise HTTPException(500, "Backup root directory does not exist")

                # Construct and verify server path
                base_path = (backup_root / server).resolve()
                try:
                    base_path.relative_to(backup_root)
                except ValueError:
                    raise HTTPException(403, "Access denied: Invalid server path")

            elif file_type in ("content_world", "content_addon"):
                content_dir_str = self.api.app_context.settings.get("paths.content")
                if not content_dir_str:
                    raise HTTPException(500, "Content directory not configured")

                # Trust anchor for content
                content_root = Path(content_dir_str).resolve()
                if not content_root.exists():
                    raise HTTPException(500, "Content root directory does not exist")

                if file_type == "content_world":
                    base_path = (content_root / "worlds").resolve()
                else:
                    base_path = (content_root / "addons").resolve()

                try:
                    base_path.relative_to(content_root)
                except ValueError:
                    raise HTTPException(
                        500, "Content subdirectory is outside content root"
                    )
            else:
                raise HTTPException(400, "Invalid file type")

            if not base_path.exists():
                raise HTTPException(404, "Base directory not found or does not exist")

            # Secure path joining
            try:
                # Join filename and resolve
                file_path = (base_path / filename).resolve()

                # Check traversal using Path.relative_to to ensure containment
                try:
                    file_path.relative_to(base_path)
                except ValueError:
                    raise HTTPException(403, "Access denied: Path traversal detected")

                if not file_path.exists() or not file_path.is_file():
                    raise HTTPException(404, "File not found")

                return FileResponse(path=file_path, filename=filename)
            except HTTPException:
                # Re-raise HTTPExceptions as-is
                raise
            except Exception as e:
                self.logger.error(f"Download error: {e}")
                raise HTTPException(500, "Internal server error during download")

    def _create_file_list_table(
        self, files: List[str], file_type: str, server: Optional[str]
    ) -> Dict:
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
                            "endpoint": f"/api/download_page/download?file_type={file_type}&filename={f}&server={server or ''}",
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

    def on_unload(self, **kwargs):
        self.logger.info(f"Plugin '{self.name}' v{self.version} unloaded.")

    def get_fastapi_routers(self, **kwargs):
        return [self.router]
