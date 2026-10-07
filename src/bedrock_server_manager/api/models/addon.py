"""Serializable addon API request and response contracts."""

from typing import Literal

from pydantic import Field

from .common import (
    ActionResponse,
    APIRequest,
    APIResponse,
    NonEmptyStr,
    PackType,
    ServerName,
    SuccessResponse,
)


class Subpack(APIResponse):
    folder_name: str
    name: str | None = None
    memory_tier: int | None = None


class InstalledAddon(APIResponse):
    name: str
    uuid: str
    version: list[int]
    status: Literal["ACTIVE", "INACTIVE", "ORPHANED"]
    path: str | None = None
    subpacks: list[Subpack] = Field(default_factory=list)
    icon: str | None = None
    active_subpack: str | None = None


class InstalledAddons(APIResponse):
    behavior_packs: list[InstalledAddon] = Field(default_factory=list)
    resource_packs: list[InstalledAddon] = Field(default_factory=list)


class ListAvailableAddonsRequest(APIRequest):
    pass


class ListAvailableAddonsResponse(SuccessResponse):
    files: list[str]


class ImportAddonRequest(APIRequest):
    server_name: ServerName
    addon_file_path: NonEmptyStr
    stop_start_server: bool = True
    restart_only_on_success: bool = True


class ImportAddonResponse(ActionResponse):
    pass


class ListInstalledAddonsRequest(APIRequest):
    server_name: ServerName


class ListInstalledAddonsResponse(SuccessResponse):
    addons: InstalledAddons


class EnableAddonRequest(APIRequest):
    server_name: ServerName
    pack_uuid: NonEmptyStr
    pack_type: PackType


class EnableAddonResponse(ActionResponse):
    pass


class DisableAddonRequest(APIRequest):
    server_name: ServerName
    pack_uuid: NonEmptyStr
    pack_type: PackType


class DisableAddonResponse(ActionResponse):
    pass


class UpdateSubpackRequest(APIRequest):
    server_name: ServerName
    pack_uuid: NonEmptyStr
    pack_type: PackType
    subpack_name: NonEmptyStr


class UpdateSubpackResponse(ActionResponse):
    pass


class UninstallAddonRequest(APIRequest):
    server_name: ServerName
    pack_uuid: NonEmptyStr
    pack_type: PackType


class UninstallAddonResponse(ActionResponse):
    pass


class ReorderAddonsRequest(APIRequest):
    server_name: ServerName
    uuids: list[NonEmptyStr]
    pack_type: PackType


class ReorderAddonsResponse(ActionResponse):
    pass
