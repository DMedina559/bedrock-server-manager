from typing import List

from pydantic import Field

from ...api.models.common import APIRequest, NonEmptyStr, PackType


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
