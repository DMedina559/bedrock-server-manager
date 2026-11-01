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
    expired_reason: Literal["absolute", "idle"] | None = None


class SecurityStatus(APIResponse):
    enabled: bool
    passkeys_enabled: bool = False
    passkey_count: int = 0
    trusted_device: bool = False
    trusted_device_expires_at: int | None = None
    required: bool = False
    recovery_codes_remaining: int
    session_id: str | None = None
    recent_until: int
    idle_timeout_seconds: int
    max_session_days: int


class VerifySecurity(APIRequest):
    remember_device: bool = False
    trusted_device_token: SecretStr | None = None
    password: SecretStr = Field(min_length=1, max_length=1024)
    otp: str = Field(default="", max_length=128)


class VerifiedSecurity(APIResponse):
    verified_until: int
    trusted_device_token: str | None = None
    trusted_device_expires_at: int | None = None


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


class TrustedDeviceInfo(APIResponse):
    id: ResourceID
    name: str
    user_agent: str
    ip_address: str
    created_at: int
    last_used_at: int
    expires_at: int
    status: Literal["active", "revoked", "expired", "invalidated"]
    current: bool


class RevokeTrustedDevices(APIRequest):
    mode: Literal["others", "all"]


class PasskeyInfo(APIResponse):
    id: ResourceID
    name: str
    transports: list[str] = Field(default_factory=list)
    aaguid: str | None = None
    user_verified: bool = False
    backup_eligible: bool = False
    backup_state: bool = False
    created_at: int
    last_used_at: int | None = None
    revoked_at: int | None = None
    active: bool


class PasskeyOptionsResponse(APIResponse):
    challenge_id: ResourceID
    public_key: dict


class CompletePasskeyRegistration(APIRequest):
    challenge_id: ResourceID
    name: str | None = Field(default=None, min_length=1, max_length=100)
    credential: dict


class RenamePasskey(APIRequest):
    name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")


class VerifyPasskeyAssertion(APIRequest):
    challenge_id: ResourceID
    credential: dict
