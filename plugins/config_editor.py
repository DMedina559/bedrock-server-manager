"""Admin editor for Bedrock script permissions, variables, and secrets."""

import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.utils.io import save_json
from bedrock_server_manager.web.deps.auth import get_admin_user, require_permissions

EditableFile = Literal[
    "permissions.json",
    "variables.json",
    "secrets.json",
]
FILES = ("permissions.json", "variables.json", "secrets.json")
MAX_BYTES = 1024 * 1024


class SaveRequest(BaseModel):
    """An edited document and the revision originally loaded."""

    model_config = ConfigDict(extra="forbid", strict=True)

    server_name: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    filename: EditableFile
    content: str = Field(max_length=MAX_BYTES)
    revision: str = Field(min_length=1, max_length=64)


class SaveResponse(BaseModel):
    """Acknowledgement returned after saving a document."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["success"] = "success"
    message: str
    revision: str


def node(kind, props=None, children=None):
    """Build a BSM JSON UI component."""
    result = {"type": kind}
    if props is not None:
        result["props"] = props
    if children is not None:
        result["children"] = children
    return result


def checked_path(root: Path, filename: EditableFile) -> Path:
    """Reject symlinks and paths outside the selected server."""
    if filename not in FILES:
        raise HTTPException(400, "Unsupported configuration file.")

    target = root
    for part in ("config", "default", filename):
        target = target / part
        if target.is_symlink():
            raise HTTPException(400, "Symbolic links are not supported.")

    if not target.resolve().is_relative_to(root.resolve()):
        raise HTTPException(400, "Invalid configuration path.")

    return target


def read_document(root: Path, filename: EditableFile):
    """Read bounded UTF-8 text and calculate its conflict-check revision."""
    target = checked_path(root, filename)
    try:
        with target.open("rb") as source:
            raw = source.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return "{}\n", "missing"

    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "This editor supports files up to 1 MiB.")

    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "The file must use UTF-8 encoding.") from None

    return content, hashlib.sha256(raw).hexdigest()


def reject_constant(value):
    """Reject nonstandard JSON constants such as NaN and Infinity."""
    raise ValueError(f"{value} is not valid JSON.")


def unique_object(pairs):
    """Reject duplicate keys instead of silently overwriting values."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


async def write_document(root: Path, request: SaveRequest) -> str:
    """Validate JSON and save through BSM's asynchronous atomic writer."""
    try:
        value = json.loads(
            request.content,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (ValueError, RecursionError) as error:
        message = (
            f"Invalid JSON at line {error.lineno}, column {error.colno}."
            if isinstance(error, json.JSONDecodeError)
            else "Invalid JSON: duplicate keys or unsupported values."
        )
        raise HTTPException(422, message) from None

    if not isinstance(value, dict):
        raise HTTPException(422, "The top-level JSON value must be an object.")

    encoded = json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise HTTPException(413, "The formatted file exceeds 1 MiB.")

    _, revision = await asyncio.to_thread(read_document, root, request.filename)
    if revision != request.revision:
        raise HTTPException(
            409,
            "The file changed elsewhere. Reload it before saving.",
        )

    target = await asyncio.to_thread(checked_path, root, request.filename)
    await save_json(value, str(target), indent=2)

    _, revision = await asyncio.to_thread(read_document, root, request.filename)
    return cast(str, revision)


class ConfigEditorPlugin(PluginBase):
    """Expose an admin-only editor through BSM's JSON UI."""

    name = "Config Editor"
    version = "1.0.0"
    author = "dmedina559"
    description = (
        "Edit server configuration options, variables, and secrets "
        "under config/default."
    )

    http_permissions = [
        ("manage", "Manage script permissions, variables, and secrets", ["admin"]),
    ]
    permissions = [
        "path:servers",
    ]

    @app_event("on_load")
    async def on_load(self, **kwargs):
        """Create routes and serialize saves made through this plugin."""
        self._save_lock = asyncio.Lock()
        self.router = APIRouter(
            prefix="/api/config-editor",
            tags=["Config Editor Plugin"],
            dependencies=[
                Depends(get_admin_user),
                Security(require_permissions, scopes=["plugin:config_editor:manage"]),
            ],
        )
        self.define_routes()

    async def server_root(self, server_name: str) -> Path:
        """Resolve a currently valid, registered Bedrock server."""
        servers = await self.api.server.get_valid_names(request={})
        if server_name not in servers.server_names:
            raise HTTPException(404, "Server not found or installation is invalid.")

        base = await self.api.runtime.get_system_path("servers")

        def resolve():
            root = base / server_name
            if root.is_symlink():
                raise HTTPException(400, "Linked server directories are unsupported.")

            root = root.resolve()
            if not root.is_relative_to(base) or not root.is_dir():
                raise HTTPException(404, "Server directory not found.")
            return root

        return cast(Path, await self.disk_operation(resolve))

    async def disk_operation(self, function, *args):
        """Run blocking file operations off the event loop."""
        try:
            if inspect.iscoroutinefunction(function):
                return await function(*args)
            return await asyncio.to_thread(function, *args)
        except HTTPException:
            raise
        except OSError as error:
            # Never log document contents, particularly secrets.
            self.logger.warning(
                "Script configuration filesystem operation failed (%s).",
                type(error).__name__,
            )
            raise HTTPException(
                500,
                "Unable to access the configuration file. "
                "Check filesystem permissions.",
            ) from None

    def define_routes(self):
        """Register the editor and typed save endpoint."""

        @self.router.get(
            "/ui",
            name="Config Editor",
            operation_id="config_editor_ui",
            tags=["plugin-json-ui"],
        )
        async def editor(
            server: str | None = Query(None),
            filename: EditableFile = Query("permissions.json", alias="file"),
        ):
            children = [
                node(
                    "Text",
                    {
                        "content": "Script Configuration",
                        "variant": "h1",
                    },
                )
            ]

            if not server:
                children.append(
                    node(
                        "Text",
                        {"content": ("Select a server from the sidebar.")},
                    )
                )
            else:
                root = await self.server_root(server)
                content, revision = await self.disk_operation(
                    read_document, root, filename
                )

                children.extend(
                    [
                        node(
                            "Text",
                            {
                                "content": (
                                    f"{server}/config/default/{filename}. "
                                    "Changing files or reloading discards "
                                    "unsaved edits."
                                )
                            },
                        ),
                        node(
                            "Select",
                            {
                                "id": "filename",
                                "label": "Configuration file",
                                "value": filename,
                                "options": [
                                    {"label": name, "value": name} for name in FILES
                                ],
                                "onChangeAction": {
                                    "type": "navigate",
                                    "dynamicParam": "file",
                                },
                            },
                        ),
                    ]
                )

                if filename == "secrets.json":
                    children.append(
                        node(
                            "Text",
                            {
                                "content": (
                                    "This document contains secrets. "
                                    "Its contents are visible in this "
                                    "editor and to administrators."
                                )
                            },
                        )
                    )

                if revision == "missing":
                    children.append(
                        node(
                            "Text",
                            {
                                "content": (
                                    "This file does not exist yet. "
                                    "Saving will create it."
                                )
                            },
                        )
                    )

                children.extend(
                    [
                        node(
                            "Textarea",
                            {
                                "id": "content",
                                "label": "JSON document",
                                "value": content,
                                "rows": 24,
                            },
                        ),
                        node(
                            "Button",
                            {
                                "label": "Save JSON",
                                "onClickAction": {
                                    "type": "api_call",
                                    "endpoint": ("/api/config-editor/save"),
                                    "includeFormState": True,
                                    "refresh": True,
                                    "payload": {
                                        "server_name": server,
                                        "filename": filename,
                                        "content": content,
                                        "revision": revision,
                                    },
                                },
                            },
                        ),
                        node(
                            "Button",
                            {
                                "label": ("Reload file — discard edits"),
                                "onClickAction": {
                                    "type": "navigate",
                                    "params": {"reload": os.urandom(8).hex()},
                                },
                            },
                        ),
                        node(
                            "Text",
                            {
                                "content": (
                                    "Changes are written to disk. "
                                    "Restart the server if required "
                                    "by its scripts."
                                )
                            },
                        ),
                    ]
                )

            return JSONResponse(
                node("Container", children=children),
                headers={"Cache-Control": "no-store"},
            )

        @self.router.post(
            "/save",
            operation_id="config_editor_save",
            response_model=SaveResponse,
        )
        async def save(request: SaveRequest):
            async with self._save_lock:
                root = await self.server_root(request.server_name)
                revision = await self.disk_operation(write_document, root, request)

            self.logger.info(
                "Updated script configuration '%s' for server '%s'.",
                request.filename,
                request.server_name,
            )

            return JSONResponse(
                SaveResponse(
                    message=(
                        f"Saved {request.filename}. "
                        "Restart the server if required by its scripts."
                    ),
                    revision=revision,
                ).model_dump(),
                headers={"Cache-Control": "no-store"},
            )
