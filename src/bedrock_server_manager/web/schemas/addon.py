from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BaseApiResponse


class AddonSchemaResponse(BaseModel):
    """Schema representing an individual addon."""

    name: str
    uuid: str
    version: List[int]
    status: str
    path: Optional[str] = None
    icon: Optional[str] = None
    subpacks: Optional[List[Dict[str, Any]]] = None


class AddonTypeGroupSchemaResponse(BaseModel):
    """Schema grouping behavior and resource packs."""

    behavior_packs: List[AddonSchemaResponse] = Field(default_factory=list)
    resource_packs: List[AddonSchemaResponse] = Field(default_factory=list)


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
