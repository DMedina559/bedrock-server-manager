"""Interactive session and factor management; never delegated to integration tokens."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security

from ...context import AppContext
from ...db.models import User
from ..access_metadata import describe_access
from ..access_policy import Permission
from ..authorization import current_authorization
from ..deps import get_app_context
from ..deps.auth import no_store, require_permissions, require_recent_session
from ..schemas import BaseApiResponse, UserResponse
from ..schemas.security import (
    CompletePasskeyRegistration,
    FactorCode,
    FactorEnrollment,
    LoginSessionInfo,
    PasskeyInfo,
    PasskeyOptionsResponse,
    RecoveryCodes,
    RenamePasskey,
    RenameSession,
    RevokeSessions,
    RevokeTrustedDevices,
    SecurityEventInfo,
    SecurityStatus,
    TrustedDeviceInfo,
    VerifiedSecurity,
    VerifyPasskeyAssertion,
    VerifySecurity,
)
from ..trusted_devices import clear_device, cookie_name, deliver_device, device_token

router = APIRouter(tags=["Account Security"], dependencies=[Depends(no_store)])


def self_owner(user):
    """Reuse only the authenticated actor's request-owned identity."""
    authorization = current_authorization.get()
    if authorization is None or authorization.user_id != user.id:
        raise HTTPException(401, "Account authorization unavailable")
    return authorization.owner_id


async def owner(context, user_id):
    async with context.storage.transaction() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(404, "Account not found")
        return user.access_id


@router.get(
    "/api/account/sessions",
    operation_id="list_login_sessions",
    response_model=list[LoginSessionInfo],
)
@describe_access("permission", additional_checks=["account-owner"])
async def sessions(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.list_sessions(
        self_owner(user), request.state.session_id
    )


@router.patch(
    "/api/account/sessions/{session_id}",
    operation_id="rename_login_session",
    response_model=BaseApiResponse,
)
@describe_access("permission", additional_checks=["session-owner"])
async def rename(
    session_id: str,
    payload: RenameSession,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await context.session_service.rename_session(
        self_owner(user), session_id, payload.name
    )
    return BaseApiResponse(status="success", message="Session renamed")


@router.delete(
    "/api/account/sessions/{session_id}",
    operation_id="revoke_login_session",
    response_model=BaseApiResponse,
)
@describe_access(
    "permission",
    additional_checks=["session-owner", "recent-verification-unless-current-session"],
)
async def revoke(
    session_id: str,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    if session_id != getattr(request.state, "session_id", None):
        await require_recent_session(request, user, context)
    await context.session_service.revoke(self_owner(user), identifier=session_id)
    return BaseApiResponse(status="success", message="Session signed out")


@router.post(
    "/api/account/sessions/revoke",
    operation_id="revoke_login_sessions",
    response_model=BaseApiResponse,
)
@describe_access(
    "permission", additional_checks=["account-owner", "recent-interactive-verification"]
)
async def revoke_many(
    payload: RevokeSessions,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await require_recent_session(request, user, context)
    await context.session_service.revoke(
        self_owner(user),
        except_id=request.state.session_id if payload.mode == "others" else None,
    )
    return BaseApiResponse(status="success", message="Sessions signed out")


@router.get(
    "/api/account/security",
    operation_id="get_account_security",
    response_model=SecurityStatus,
)
@describe_access("permission", additional_checks=["account-owner"])
async def status(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    record = await context.session_service.validate(
        request.state.session_id, touch=False
    )
    trusted = await context.trusted_device_service.validate(
        self_owner(user), device_token(request, self_owner(user))
    )
    recent_until = record.verified_at + 300 if record else 0
    if record and record.verified_device_id:
        async with context.storage.transaction() as session:
            source = await context.trusted_device_service.live_record(
                session, self_owner(user), record.verified_device_id
            )
            recent_until = min(recent_until, source.expires_at) if source else 0
    return SecurityStatus(
        trusted_device=trusted is not None,
        trusted_device_expires_at=trusted.expires_at if trusted else None,
        **await context.session_service.status(self_owner(user)),
        session_id=request.state.session_id,
        required=user.role == "admin"
        and context.settings.get("security.require_admin_mfa", False),
        recent_until=recent_until,
        idle_timeout_seconds=context.session_service.idle_seconds(),
        max_session_days=context.settings.get("security.session_max_days", 28),
    )


@router.post(
    "/api/account/security/verify",
    operation_id="verify_account_security",
    response_model=VerifiedSecurity,
)
@describe_access("permission", additional_checks=["account-owner"])
async def verify(
    payload: VerifySecurity,
    request: Request,
    response: Response,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    now, proof = await context.session_service.verify_recent(
        user,
        request.state.session_id,
        payload.password.get_secret_value(),
        payload.otp,
        request.client.host if request.client else "",
        device_token(request, self_owner(user), payload.trusted_device_token),
    )
    issued = (
        await context.trusted_device_service.remember(proof, request)
        if payload.remember_device
        else None
    )
    return VerifiedSecurity(
        verified_until=now + 300,
        **deliver_device(
            response,
            request,
            self_owner(user),
            issued,
            cookie_mode=getattr(request.state, "credential_source", None) == "cookie",
        ),
    )


@router.get(
    "/api/account/security/activity",
    operation_id="list_security_activity",
    response_model=list[SecurityEventInfo],
)
@describe_access("permission", additional_checks=["account-owner"])
async def activity(
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.activity(self_owner(user))


@router.post(
    "/api/account/security/mfa/enroll",
    operation_id="enroll_account_mfa",
    response_model=FactorEnrollment,
)
@describe_access(
    "permission", additional_checks=["account-owner", "recent-interactive-verification"]
)
async def enroll(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await require_recent_session(request, user, context)
    return await context.session_service.enrollment(self_owner(user), user.username)


@router.post(
    "/api/account/security/mfa/confirm",
    operation_id="confirm_account_mfa",
    response_model=RecoveryCodes,
)
@describe_access(
    "permission", additional_checks=["account-owner", "recent-interactive-verification"]
)
async def confirm(
    payload: FactorCode,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await require_recent_session(request, user, context)
    await context.session_service.throttle(
        user.username, request.client.host if request.client else "", "mfa"
    )
    identity = self_owner(user)
    result = await context.session_service.confirm_enrollment(
        identity, payload.code, keep_session_id=request.state.session_id
    )
    return result


@router.post(
    "/api/account/security/mfa/recovery-codes",
    operation_id="rotate_account_recovery_codes",
    response_model=RecoveryCodes,
)
@describe_access(
    "permission", additional_checks=["account-owner", "recent-interactive-verification"]
)
async def recovery(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await require_recent_session(request, user, context)
    current_device = await context.trusted_device_service.validate(
        self_owner(user), device_token(request, self_owner(user))
    )
    return await context.session_service.change_factor(
        self_owner(user),
        keep_session_id=request.state.session_id,
        keep_trusted_device=current_device,
    )


@router.delete(
    "/api/account/security/mfa",
    operation_id="disable_account_mfa",
    response_model=BaseApiResponse,
)
@describe_access(
    "permission",
    additional_checks=[
        "account-owner",
        "recent-interactive-verification",
        "administrator-mfa-policy",
    ],
)
async def disable(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    identity = self_owner(user)
    if (
        user.role == "admin"
        and context.settings.get("security.require_admin_mfa", False)
        and not await context.session_service.has_active_passkeys(identity)
    ):
        raise HTTPException(
            403,
            "Administrator MFA is required; enroll a replacement factor or use local recovery",
        )
    await require_recent_session(request, user, context)
    await context.session_service.change_factor(
        identity, disable=True, keep_session_id=request.state.session_id
    )
    return BaseApiResponse(status="success", message="Second factor disabled")


@router.get(
    "/api/access/users/{user_id}/sessions",
    operation_id="list_account_login_sessions",
    response_model=list[LoginSessionInfo],
)
async def admin_sessions(
    user_id: int,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_ADMIN]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.list_sessions(await owner(context, user_id))


@router.delete(
    "/api/access/users/{user_id}/sessions/{session_id}",
    operation_id="revoke_account_login_session",
    response_model=BaseApiResponse,
)
async def admin_revoke(
    user_id: int,
    session_id: str,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_ADMIN]
    ),
    context: AppContext = Depends(get_app_context),
):
    await context.session_service.revoke(
        await owner(context, user_id),
        identifier=session_id,
        reason="admin_session_revoked",
    )
    await context.session_service.event(
        user.id, "admin_session_revoked", target_user_id=user_id, session_id=session_id
    )
    return BaseApiResponse(status="success", message="Session signed out")


@router.delete(
    "/api/access/users/{user_id}/mfa",
    operation_id="reset_account_mfa",
    response_model=BaseApiResponse,
)
@describe_access("permission", additional_checks=["other-account-only"])
async def admin_reset_mfa(
    user_id: int,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_ADMIN]
    ),
    context: AppContext = Depends(get_app_context),
):
    if user_id == user.id:
        raise HTTPException(
            403, "Use your account security settings to disable your own second factor"
        )
    identity = await owner(context, user_id)
    await context.session_service.change_factor(
        identity, disable=True, reset_passkeys=True
    )
    await context.session_service.event(
        user.id, "admin_mfa_reset", target_user_id=user_id
    )
    return BaseApiResponse(
        status="success",
        message="Second factor reset; the account's logins were signed out",
    )


@router.post(
    "/api/access/users/{user_id}/sessions/revoke",
    operation_id="revoke_account_login_sessions",
    response_model=BaseApiResponse,
)
async def admin_revoke_all(
    user_id: int,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_ADMIN]
    ),
    context: AppContext = Depends(get_app_context),
):
    await context.session_service.revoke(
        await owner(context, user_id), reason="admin_sessions_revoked"
    )
    await context.session_service.event(
        user.id, "admin_sessions_revoked", target_user_id=user_id
    )
    return BaseApiResponse(status="success", message="Account sessions signed out")


@router.get(
    "/api/account/security/devices",
    operation_id="list_trusted_devices",
    response_model=list[TrustedDeviceInfo],
)
@describe_access("permission", additional_checks=["account-owner"])
async def trusted_devices(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.trusted_device_service.list(
        self_owner(user), device_token(request, self_owner(user))
    )


@router.delete(
    "/api/account/security/devices/{device_id}",
    operation_id="revoke_trusted_device",
    response_model=BaseApiResponse,
)
@describe_access("permission", additional_checks=["account-owner"])
async def revoke_trusted_device(
    device_id: str,
    request: Request,
    response: Response,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    owner_id = self_owner(user)
    await context.trusted_device_service.revoke(owner_id, identifier=device_id)
    if (
        getattr(request.state, "credential_source", None) == "cookie"
        and context.trusted_device_service.identifier(
            request.cookies.get(cookie_name(owner_id))
        )
        == device_id
    ):
        clear_device(response, request, owner_id)
    return BaseApiResponse(status="success", message="Remembered device removed")


@router.post(
    "/api/account/security/devices/revoke",
    operation_id="revoke_trusted_devices",
    response_model=BaseApiResponse,
)
@describe_access("permission", additional_checks=["account-owner"])
async def revoke_trusted_devices(
    payload: RevokeTrustedDevices,
    request: Request,
    response: Response,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    owner_id = self_owner(user)
    current = await context.trusted_device_service.validate(
        owner_id, device_token(request, owner_id)
    )
    except_id = current.id if current and payload.mode == "others" else None
    await context.trusted_device_service.revoke(owner_id, except_id=except_id)
    if (
        payload.mode == "all"
        and getattr(request.state, "credential_source", None) == "cookie"
    ):
        clear_device(response, request, owner_id)
    return BaseApiResponse(status="success", message="Remembered devices removed")


@router.get(
    "/api/account/security/passkeys",
    operation_id="list_passkeys",
    response_model=list[PasskeyInfo],
)
@describe_access("permission", additional_checks=["account-owner"])
async def list_passkeys(
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.list_passkeys(self_owner(user))


@router.post(
    "/api/account/security/passkeys/register/options",
    operation_id="begin_passkey_registration",
    response_model=PasskeyOptionsResponse,
)
@describe_access(
    "permission", additional_checks=["account-owner", "recent-interactive-verification"]
)
async def begin_passkey_registration(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await require_recent_session(request, user, context)
    return await context.session_service.begin_passkey_registration(
        self_owner(user), user.username, request
    )


@router.post(
    "/api/account/security/passkeys/register/verify",
    operation_id="complete_passkey_registration",
    response_model=PasskeyInfo,
    status_code=201,
)
@describe_access(
    "permission", additional_checks=["account-owner", "recent-interactive-verification"]
)
async def complete_passkey_registration(
    payload: CompletePasskeyRegistration,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await require_recent_session(request, user, context)
    return await context.session_service.complete_passkey_registration(
        self_owner(user), payload, request
    )


@router.patch(
    "/api/account/security/passkeys/{passkey_id}",
    operation_id="rename_passkey",
    response_model=PasskeyInfo,
)
@describe_access("permission", additional_checks=["account-owner"])
async def rename_passkey(
    passkey_id: str,
    payload: RenamePasskey,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.rename_passkey(
        self_owner(user), passkey_id, payload.name
    )


@router.delete(
    "/api/account/security/passkeys/{passkey_id}",
    operation_id="revoke_passkey",
    response_model=BaseApiResponse,
)
@describe_access(
    "permission",
    additional_checks=[
        "account-owner",
        "recent-interactive-verification",
        "administrator-mfa-policy",
    ],
)
async def revoke_passkey(
    passkey_id: str,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await require_recent_session(request, user, context)
    await context.session_service.revoke_passkey(
        self_owner(user), passkey_id, is_admin_role=(user.role == "admin")
    )
    return BaseApiResponse(status="success", message="Passkey removed")


@router.post(
    "/api/account/security/passkeys/verify/options",
    operation_id="begin_passkey_step_up",
    response_model=PasskeyOptionsResponse,
)
@describe_access("permission", additional_checks=["account-owner"])
async def begin_passkey_step_up(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.begin_passkey_authentication(
        request, purpose="verify", owner_id=self_owner(user)
    )


@router.post(
    "/api/account/security/passkeys/verify",
    operation_id="verify_account_security_passkey",
    response_model=VerifiedSecurity,
)
@describe_access("permission", additional_checks=["account-owner"])
async def verify_passkey_step_up(
    payload: VerifyPasskeyAssertion,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    now = await context.session_service.verify_recent_passkey(
        user, request.state.session_id, payload, request
    )
    return VerifiedSecurity(verified_until=now + 300)


@router.get(
    "/api/access/users/{user_id}/passkeys",
    operation_id="list_account_passkeys",
    response_model=list[PasskeyInfo],
)
async def admin_list_passkeys(
    user_id: int,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_ADMIN]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.list_passkeys(await owner(context, user_id))
