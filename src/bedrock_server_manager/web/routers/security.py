"""Interactive session and factor management; never delegated to integration tokens."""

from fastapi import APIRouter, Depends, HTTPException, Request, Security

from ...context import AppContext
from ...db.models import LoginSession, User
from ..access_policy import Permission
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import BaseApiResponse, UserResponse
from ..schemas.security import (
    FactorCode,
    FactorEnrollment,
    LoginSessionInfo,
    RecoveryCodes,
    RenameSession,
    RevokeSessions,
    SecurityEventInfo,
    SecurityStatus,
    VerifiedSecurity,
    VerifySecurity,
)
from .access import no_store

router = APIRouter(tags=["Account Security"], dependencies=[Depends(no_store)])


async def owner(context, user_id):
    async with context.storage.transaction() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(404, "Account not found")
        return user.access_id


async def recent(request, user, context):
    return await context.session_service.require_recent(
        user, getattr(request.state, "session_id", None)
    )


@router.get(
    "/api/account/sessions",
    operation_id="list_login_sessions",
    response_model=list[LoginSessionInfo],
)
async def sessions(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.list_sessions(
        await owner(context, user.id), request.state.session_id
    )


@router.patch(
    "/api/account/sessions/{session_id}",
    operation_id="rename_login_session",
    response_model=BaseApiResponse,
)
async def rename(
    session_id: str,
    payload: RenameSession,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    identity = await owner(context, user.id)
    async with context.storage.transaction() as session:
        record = await session.get(LoginSession, session_id)
        if record is None or record.owner_id != identity:
            raise HTTPException(404, "Session not found")
        record.name = payload.name.strip()
    return BaseApiResponse(status="success", message="Session renamed")


@router.delete(
    "/api/account/sessions/{session_id}",
    operation_id="revoke_login_session",
    response_model=BaseApiResponse,
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
        await recent(request, user, context)
    await context.session_service.revoke(
        await owner(context, user.id), identifier=session_id
    )
    return BaseApiResponse(status="success", message="Session signed out")


@router.post(
    "/api/account/sessions/revoke",
    operation_id="revoke_login_sessions",
    response_model=BaseApiResponse,
)
async def revoke_many(
    payload: RevokeSessions,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await recent(request, user, context)
    await context.session_service.revoke(
        await owner(context, user.id),
        except_id=request.state.session_id if payload.mode == "others" else None,
    )
    return BaseApiResponse(status="success", message="Sessions signed out")


@router.get(
    "/api/account/security",
    operation_id="get_account_security",
    response_model=SecurityStatus,
)
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
    return SecurityStatus(
        **await context.session_service.status(await owner(context, user.id)),
        session_id=request.state.session_id,
        required=user.role == "admin"
        and context.settings.get("security.require_admin_mfa", False),
        recent_until=record.verified_at + 300 if record else 0,
        idle_timeout_seconds=context.session_service.idle_seconds(),
        max_session_days=context.settings.get("security.session_max_days", 28),
    )


@router.post(
    "/api/account/security/verify",
    operation_id="verify_account_security",
    response_model=VerifiedSecurity,
)
async def verify(
    payload: VerifySecurity,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    now = await context.session_service.verify_recent(
        user,
        request.state.session_id,
        payload.password.get_secret_value(),
        payload.otp,
        request.client.host if request.client else "",
    )
    return VerifiedSecurity(verified_until=now + 300)


@router.get(
    "/api/account/security/activity",
    operation_id="list_security_activity",
    response_model=list[SecurityEventInfo],
)
async def activity(
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.session_service.activity(await owner(context, user.id))


@router.post(
    "/api/account/security/mfa/enroll",
    operation_id="enroll_account_mfa",
    response_model=FactorEnrollment,
)
async def enroll(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await recent(request, user, context)
    return await context.session_service.enrollment(
        await owner(context, user.id), user.username
    )


@router.post(
    "/api/account/security/mfa/confirm",
    operation_id="confirm_account_mfa",
    response_model=RecoveryCodes,
)
async def confirm(
    payload: FactorCode,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await recent(request, user, context)
    await context.session_service.throttle(
        user.username, request.client.host if request.client else "", "mfa"
    )
    identity = await owner(context, user.id)
    result = await context.session_service.confirm_enrollment(
        identity, payload.code, keep_session_id=request.state.session_id
    )
    return result


@router.post(
    "/api/account/security/mfa/recovery-codes",
    operation_id="rotate_account_recovery_codes",
    response_model=RecoveryCodes,
)
async def recovery(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await recent(request, user, context)
    return await context.session_service.change_factor(
        await owner(context, user.id), keep_session_id=request.state.session_id
    )


@router.delete(
    "/api/account/security/mfa",
    operation_id="disable_account_mfa",
    response_model=BaseApiResponse,
)
async def disable(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    if user.role == "admin" and context.settings.get(
        "security.require_admin_mfa", False
    ):
        raise HTTPException(
            403,
            "Administrator MFA is required; enroll a replacement factor or use local recovery",
        )
    await recent(request, user, context)
    identity = await owner(context, user.id)
    await context.session_service.change_factor(
        identity, disable=True, keep_session_id=request.state.session_id
    )
    return BaseApiResponse(status="success", message="Second factor disabled")


@router.post(
    "/api/account/tokens/revoke-all",
    operation_id="revoke_all_integration_tokens",
    response_model=BaseApiResponse,
)
async def revoke_credentials(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.TOKENS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await recent(request, user, context)
    await context.session_service.revoke_credentials(await owner(context, user.id))
    return BaseApiResponse(status="success", message="Integration credentials revoked")


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
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_ADMIN]
    ),
    context: AppContext = Depends(get_app_context),
):
    await recent(request, user, context)
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
async def admin_reset_mfa(
    user_id: int,
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_ADMIN]
    ),
    context: AppContext = Depends(get_app_context),
):
    await recent(request, user, context)
    if user_id == user.id:
        raise HTTPException(
            403, "Use your account security settings to disable your own second factor"
        )
    identity = await owner(context, user_id)
    await context.session_service.change_factor(identity, disable=True)
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
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SESSIONS_ADMIN]
    ),
    context: AppContext = Depends(get_app_context),
):
    await recent(request, user, context)
    await context.session_service.revoke(
        await owner(context, user_id), reason="admin_sessions_revoked"
    )
    await context.session_service.event(
        user.id, "admin_sessions_revoked", target_user_id=user_id
    )
    return BaseApiResponse(status="success", message="Account sessions signed out")
