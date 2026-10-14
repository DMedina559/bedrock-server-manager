from typing import Optional

from ...api.models.common import APIRequest, APIResponse
from ...contracts import Password
from ...state.types import UserRole


class UserResponse(APIResponse):
    """Pydantic model representing a user."""

    id: int
    username: str
    identity_type: Optional[str] = None
    role: UserRole
    is_active: bool
    theme: str = "default"


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
