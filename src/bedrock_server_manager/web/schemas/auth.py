from typing import Literal, Optional

from pydantic import Field

from ...api.models.common import APIRequest, APIResponse
from ...contracts import Password
from ...state.models import UserRole


class GenerateTokenPayload(APIRequest):
    """Request payload for generating a registration token.

    :ivar role: The role to assign to the user registering with this token.
    """

    role: UserRole


class TokenResponse(APIResponse):
    """Response model for successful authentication, providing an access token."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    message: Optional[str] = None


class UserLoginPayload(APIRequest):
    """Request model for user login credentials."""

    username: str = Field(..., min_length=1, max_length=80)
    password: Password
    remember_me: bool = Field(default=False)


class SetupAccountResponse(TokenResponse):
    """First account creation returns the same session credentials as login."""

    status: Literal["success"] = "success"
    message: str
