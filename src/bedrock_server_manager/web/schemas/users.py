from typing import Optional

from pydantic import Field

from ...api.models.common import APIRequest, APIResponse
from ...contracts import Password
from ...state.models import UserRole


class UserResponse(APIResponse):
    """Pydantic model representing a user."""

    id: int
    username: str
    identity_type: Optional[str] = None
    role: UserRole
    is_active: bool
    theme: str = "default"


class CurrentAccountResponse(UserResponse):
    """Current account with sorted role-derived HTTP capabilities."""

    permissions: list[str] = Field(default_factory=list)
    policy_revision: str | None = None
    server_access: str = "all"
    credential_id: str | None = None
    server_permissions: dict[str, list[str]] = Field(default_factory=dict)


class UpdateUserRolePayload(APIRequest):
    """Request payload for updating a user's role.

    :ivar role: The new role.
    """

    role: UserRole


class ThemeUpdatePayload(APIRequest):
    """Request payload for updating the user's theme.

    :ivar theme: The new theme name.
    """

    theme: str


class ProfileUpdatePayload(APIRequest):
    """Request payload for updating user profile details.

    :ivar full_name: The user's full name.

    :ivar email: The user's email address.
    """

    full_name: str
    email: str


class ChangePasswordPayload(APIRequest):
    """Request payload for changing the user's password.

    :ivar current_password: The current password for verification.

    :ivar new_password: The new password.
    """

    current_password: Password
    new_password: Password
