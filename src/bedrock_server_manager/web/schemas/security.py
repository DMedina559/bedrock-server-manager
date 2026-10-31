"""Public session metadata and one-time factor setup responses."""

from typing import Literal

from pydantic import Field, SecretStr

from ...api.models.common import APIRequest, APIResponse
from .access import ResourceID


class LoginSessionInfo(APIResponse):
    id: ResourceID
    name: str
    user_agent: str
    ip_address: str
    created_at: int
    last_seen_at: int
    expires_at: int
    revoked_at: int | None = None
    current: bool
    connected: bool
    active: bool


class SecurityStatus(APIResponse):
    enabled: bool
    recovery_codes_remaining: int
    session_id: str | None = None
    recent_until: int
    idle_timeout_seconds: int
    max_session_days: int


class VerifySecurity(APIRequest):
    password: SecretStr = Field(min_length=1, max_length=1024)
    otp: str = Field(default="", max_length=128)


class VerifiedSecurity(APIResponse):
    verified_until: int


class RenameSession(APIRequest):
    name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")


class RevokeSessions(APIRequest):
    mode: Literal["others", "all"]


class FactorCode(APIRequest):
    code: str = Field(min_length=6, max_length=128)


class FactorEnrollment(APIResponse):
    secret: str
    provisioning_uri: str
    qr_svg: str


class RecoveryCodes(APIResponse):
    recovery_codes: list[str]


class SecurityEventInfo(APIResponse):
    id: str
    action: str
    timestamp: int
    details: dict
