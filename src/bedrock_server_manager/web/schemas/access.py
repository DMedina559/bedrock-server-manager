"""Administrative access contracts; token secrets appear only on creation."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from ...api.models.common import APIRequest, APIResponse

ResourceID = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]


class CreateIntegrationToken(APIRequest):
    name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")
    permissions: list[str] = Field(min_length=1, max_length=256)
    server_ids: list[ResourceID] | None = Field(default=None, max_length=1000)
    expires_in_days: int | None = Field(default=30, ge=1, le=365)


class IntegrationTokenInfo(APIResponse):
    id: ResourceID
    name: str
    permissions: list[str]
    server_ids: list[ResourceID] | None = None
    created_at: int
    expires_at: int | None
    last_used_at: int | None = None
    revoked_at: int | None = None


class CreatedIntegrationToken(APIResponse):
    token: str
    credential: IntegrationTokenInfo


class ServerGrant(APIRequest):
    server_id: ResourceID
    permissions: list[str] = Field(min_length=1, max_length=256)


class SetServerAccess(APIRequest):
    mode: Literal["all", "assigned"]
    grants: list[ServerGrant] = Field(default_factory=list, max_length=1000)


class AccountServerAccessInfo(APIResponse):
    user_id: int
    mode: Literal["all", "assigned"]
    grants: list[ServerGrant]
    policy_revision: str


class AccessServerInfo(APIResponse):
    id: ResourceID
    name: str
    permissions: list[str]


class AccessPolicyInfo(APIResponse):
    revision: str
    permissions: dict[str, str]
    server_permissions: list[str]
    token_permissions: list[str]
    role_permissions: dict[str, list[str]]
