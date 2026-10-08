from typing import Optional

from pydantic import BaseModel, Field

from ...api.models.common import APIRequest
from ...state.types import UserRole


class GenerateTokenPayload(APIRequest):
    """
    Request payload for generating a registration token.

    Attributes:
        role (str): The role to assign to the user registering with this token.
    """

    role: UserRole


class TokenResponse(BaseModel):
    """Response model for successful authentication, providing an access token."""

    access_token: str
    token_type: str
    message: Optional[str] = None


class UserLoginPayload(APIRequest):
    """Request model for user login credentials."""

    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1)
    remember_me: bool = Field(default=False)
