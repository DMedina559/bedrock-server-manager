from typing import List, Optional

from pydantic import Field

from ...api.models.addon import InstalledAddon, InstalledAddons
from ...api.models.common import APIRequest, NonEmptyStr, PackType
from .base import BaseApiResponse

# Keep public schema names while sharing the API data contracts.
AddonSchemaResponse = InstalledAddon
AddonTypeGroupSchemaResponse = InstalledAddons


class AddonListResponse(BaseApiResponse):
    """Response model for retrieving all addons on a server."""

    addons: Optional[AddonTypeGroupSchemaResponse] = None


class AddonActionPayload(APIRequest):
    """Request model for modifying a specific addon (e.g. enable, disable, uninstall)."""

    pack_uuid: NonEmptyStr = Field(..., description="The UUID of the pack.")
    pack_type: PackType = Field(
        ..., description="The type of the pack: 'behavior' or 'resource'."
    )


class AddonSubpackPayload(APIRequest):
    """Request model for changing the active subpack of an addon."""

    pack_uuid: NonEmptyStr = Field(..., description="The UUID of the pack.")
    pack_type: PackType = Field(
        ..., description="The type of the pack: 'behavior' or 'resource'."
    )
    subpack_name: NonEmptyStr = Field(
        ..., description="The folder name of the subpack to activate."
    )


class AddonReorderPayload(APIRequest):
    """Request model for reordering active addons."""

    pack_type: PackType = Field(
        ..., description="The type of the pack: 'behavior' or 'resource'."
    )
    uuids: List[NonEmptyStr] = Field(
        ...,
        description="The exact list of currently active UUIDs in the new desired order.",
    )
