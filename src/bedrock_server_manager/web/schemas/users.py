from typing import Optional

from ...api.models.common import APIRequest, APIResponse
from ...contracts import Password
from ...state.types import UserRole


class UserResponse(APIResponse):
    """
    Pydantic model representing a user.

    Attributes:
        id (int): The user's ID.
        username (str): The user's username.
        identity_type (str): The type of identity (e.g., "local").
        role (str): The user's role.
        is_active (bool): Whether the user is active.
        theme (str): The user's preferred theme. Defaults to "default".
    """

    id: int
    username: str
    identity_type: Optional[str] = None
    role: UserRole
    is_active: bool
    theme: str = "default"


class UpdateUserRolePayload(APIRequest):
    """
    Request payload for updating a user's role.

    Attributes:
        role (str): The new role.
    """

    role: UserRole


class ThemeUpdatePayload(APIRequest):
    """
    Request payload for updating the user's theme.

    Attributes:
        theme (str): The new theme name.
    """

    theme: str


class ProfileUpdatePayload(APIRequest):
    """
    Request payload for updating user profile details.

    Attributes:
        full_name (str): The user's full name.
        email (str): The user's email address.
    """

    full_name: str
    email: str


class ChangePasswordPayload(APIRequest):
    """
    Request payload for changing the user's password.

    Attributes:
        current_password (str): The current password for verification.
        new_password (str): The new password.
    """

    current_password: Password
    new_password: Password
