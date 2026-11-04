from typing import Dict, List, Literal, Optional

from pydantic import Field

from ...models.allowlist import AllowlistAddPayload, AllowlistRemovePayload
from ...models.common import APIResponse, ItemResult
from ...models.install import InstallServerPayload
from ...models.permissions import PermissionsSetPayload, PlayerPermissionPayload
from ...models.properties import PropertiesPayload
from .base import BaseApiResponse, TaskAcceptedResponse


class CustomZipsResponse(BaseApiResponse):
    """Response model for custom zips list."""

    custom_zips: List[str]


class PermissionsUpdateResponse(BaseApiResponse):
    """Response model for permissions update."""

    updated: int = Field(default=0, ge=0)
    outcomes: dict[str, ItemResult] = Field(default_factory=dict)
    errors: Optional[Dict[str, str]] = None


class InstallConfirmationResponse(APIResponse):
    status: Literal["confirm_needed"] = "confirm_needed"
    message: str
    server_name: str


class InstallationAcceptedResponse(TaskAcceptedResponse):
    server_name: str


InstallServerResponse = InstallConfirmationResponse | InstallationAcceptedResponse

__all__ = [
    "AllowlistAddPayload",
    "AllowlistRemovePayload",
    "CustomZipsResponse",
    "InstallConfirmationResponse",
    "InstallServerPayload",
    "InstallServerResponse",
    "InstallationAcceptedResponse",
    "PermissionsSetPayload",
    "PermissionsUpdateResponse",
    "PlayerPermissionPayload",
    "PropertiesPayload",
]
