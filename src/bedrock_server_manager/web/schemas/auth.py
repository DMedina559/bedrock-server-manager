from typing import Literal, Optional

from pydantic import Field

from ...api.models.common import APIRequest, APIResponse
from ...contracts import NewPassword
from ...state.models import UserRole


class GenerateTokenPayload(APIRequest):
    """Request payload for generating a registration token.

    :ivar role: The role to assign to the user registering with this token.
    """

    role: UserRole


class TokenResponse(APIResponse):
    """Response model for successful authentication, providing an access token."""

    access_token: str = Field(
        description="Bearer JWT; empty in explicitly negotiated cookie mode, where the credential is HttpOnly"
    )
    trusted_device_token: str | None = Field(
        default=None,
        description="One-time remembered-device credential; omitted in cookie mode. Store only when explicitly requested.",
    )
    trusted_device_expires_at: int | None = None
    token_type: Literal["bearer"] = "bearer"
    message: Optional[str] = None


class UserLoginPayload(APIRequest):
    """Request model for user login credentials."""

    username: str = Field(..., min_length=1, max_length=80)
    password: NewPassword
    remember_me: bool = Field(default=False)


class SetupAccountResponse(TokenResponse):
    """First account creation returns the same session credentials as login."""

    status: Literal["success"] = "success"
    message: str


class PasskeyLoginOptionsRequest(APIRequest):
    """Optional username hint when requesting WebAuthn authentication options."""

    username: str | None = Field(default=None, max_length=80)


class PasskeyLoginVerifyRequest(APIRequest):
    """WebAuthn assertion payload for passwordless passkey login."""

    challenge_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")
    credential: dict
    remember_me: bool = Field(default=False)
