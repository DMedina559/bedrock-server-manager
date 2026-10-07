from typing import List, Optional

from pydantic import BaseModel, Field

from ...api.models.addon import InstalledAddon, InstalledAddons
from .base import BaseApiResponse

# Keep public schema names while sharing the API data contracts.
AddonSchemaResponse = InstalledAddon
AddonTypeGroupSchemaResponse = InstalledAddons


class AddonListResponse(BaseApiResponse):
    """Response model for retrieving all addons on a server."""

    addons: Optional[AddonTypeGroupSchemaResponse] = None


class AddonActionPayload(BaseModel):
    """Request model for modifying a specific addon (e.g. enable, disable, uninstall)."""

    pack_uuid: str = Field(..., description="The UUID of the pack.")
    pack_type: str = Field(
        ..., description="The type of the pack: 'behavior' or 'resource'."
    )


class AddonSubpackPayload(BaseModel):
    """Request model for changing the active subpack of an addon."""

    pack_uuid: str = Field(..., description="The UUID of the pack.")
    pack_type: str = Field(
        ..., description="The type of the pack: 'behavior' or 'resource'."
    )
    subpack_name: Optional[str] = Field(
        None, description="The folder name of the subpack to activate."
    )

    model_config = {"extra": "allow"}


class AddonReorderPayload(BaseModel):
    """Request model for reordering active addons."""

    pack_type: str = Field(
        ..., description="The type of the pack: 'behavior' or 'resource'."
    )
    uuids: List[str] = Field(
        ...,
        description="The exact list of currently active UUIDs in the new desired order.",
    )
