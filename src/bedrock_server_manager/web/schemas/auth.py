from typing import Optional

from pydantic import BaseModel, Field


class GenerateTokenRequest(BaseModel):
    """
    Request payload for generating a registration token.

    Attributes:
        role (str): The role to assign to the user registering with this token.
    """

    role: str


class RegisterUserRequest(BaseModel):
    """
    Request payload for user registration.

    Attributes:
        username (str): The desired username.
        password (str): The desired password.
    """

    username: str
    password: str


class Token(BaseModel):
    """Response model for successful authentication, providing an access token."""

    access_token: str
    token_type: str
    message: Optional[str] = None


class UserLogin(BaseModel):
    """Request model for user login credentials."""

    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1)
