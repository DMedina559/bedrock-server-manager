"""Serializable addon API and HTTP contracts."""

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


class AddonActionPayload(APIRequest):
    """Request model for modifying a specific addon (e.g. enable, disable, uninstall)."""

    pack_uuid: NonEmptyStr = Field(..., description="The UUID of the pack.")
    pack_type: PackType = Field(
        ..., description="The type of the pack: 'behavior' or 'resource'."
    )


class AddonSubpackPayload(AddonActionPayload):
    """Request model for changing the active subpack of an addon."""

    subpack_name: NonEmptyStr = Field(
        ..., description="The folder name of the subpack to activate."
    )


class AddonReorderPayload(APIRequest):
    """Request model for reordering active addons."""

    pack_type: PackType = Field(
        ..., description="The type of the pack: 'behavior' or 'resource'."
    )
    uuids: list[NonEmptyStr] = Field(
        ...,
        description="The exact list of currently active UUIDs in the new desired order.",
    )


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
    server_name: ServerName


class ListInstalledAddonsRequest(APIRequest):
    server_name: ServerName


class ListInstalledAddonsResponse(SuccessResponse):
    addons: InstalledAddons


class EnableAddonRequest(AddonActionPayload):
    server_name: ServerName


class EnableAddonResponse(ActionResponse):
    server_name: ServerName


class DisableAddonRequest(AddonActionPayload):
    server_name: ServerName


class DisableAddonResponse(ActionResponse):
    server_name: ServerName


class UpdateSubpackRequest(AddonSubpackPayload):
    server_name: ServerName


class UpdateSubpackResponse(ActionResponse):
    server_name: ServerName


class UninstallAddonRequest(AddonActionPayload):
    server_name: ServerName


class UninstallAddonResponse(ActionResponse):
    server_name: ServerName


class ReorderAddonsRequest(AddonReorderPayload):
    server_name: ServerName


class ReorderAddonsResponse(ActionResponse):
    server_name: ServerName
