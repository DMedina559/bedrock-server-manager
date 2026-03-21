from typing import Optional

from pydantic import BaseModel


class UserResponse(BaseModel):
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
    role: str
    is_active: bool
    theme: str = "default"


class CreateUserPayload(BaseModel):
    """
    Request payload for creating a new user.

    Attributes:
        username (str): The new username.
        password (str): The new password.
        role (str): The role for the new user.
    """

    username: str
    password: str
    role: str


class UpdateUserRolePayload(BaseModel):
    """
    Request payload for updating a user's role.

    Attributes:
        role (str): The new role.
    """

    role: str


class ThemeUpdatePayload(BaseModel):
    """
    Request payload for updating the user's theme.

    Attributes:
        theme (str): The new theme name.
    """

    theme: str


class ProfileUpdatePayload(BaseModel):
    """
    Request payload for updating user profile details.

    Attributes:
        full_name (str): The user's full name.
        email (str): The user's email address.
    """

    full_name: str
    email: str


class ChangePasswordPayload(BaseModel):
    """
    Request payload for changing the user's password.

    Attributes:
        current_password (str): The current password for verification.
        new_password (str): The new password.
    """

    current_password: str
    new_password: str
