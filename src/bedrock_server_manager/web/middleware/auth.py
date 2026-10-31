import hashlib
import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

from ..auth import get_jwt_secret_key
from ..deps.auth import get_current_user_optional
from ..origin import browser_origin
from .ingress import route_path


async def add_user_to_request(request: Request, call_next):
    """Middleware that checks for a valid authentication token/cookie and adds the
    current user to ``request.state.current_user``.
    """

    path = route_path(request.scope)

    # 1. Bypass database lookup for static files to prevent SQLite locking
    if (
        path.startswith(
            ("/static", "/assets", "/image", "/app/static", "/app/assets", "/app/image")
        )
        or path == "/favicon.ico"
    ):
        request.state.current_user = None
        return await call_next(request)

    # 2. Normal auth lookup for API and Page requests
    user = await get_current_user_optional(request)
    request.state.current_user = user
    request.state.authentication_resolved = True
    from ..authorization import current_authorization, operation_permissions

    authorization = getattr(request.state, "authorization", None)
    csrf = None
    session_id = getattr(request.state, "session_id", None)
    if user is not None and session_id:
        secret = await get_jwt_secret_key(request.app.state.app_context.settings)
        csrf = hmac.new(
            secret.encode(), ("csrf:" + session_id).encode(), hashlib.sha256
        ).hexdigest()
    unsafe = request.method not in {"GET", "HEAD", "OPTIONS"} or path == "/auth/logout"
    if unsafe:
        origin = request.headers.get("origin")
        allowed = request.app.state.app_context.settings.get("web.cors_origins", ())
        establishing = path in {"/auth/token", "/api/setup/create-first-user"}
        cookie_mutation = (
            getattr(request.state, "credential_source", None) == "cookie"
            and not establishing
        )
        check_origin = cookie_mutation or (
            establishing and request.headers.get("x-bsm-auth-mode") == "cookie"
        )
        if (
            check_origin
            and origin
            and origin != browser_origin(request)
            and origin not in allowed
        ):
            return JSONResponse(
                {"detail": "Origin is not allowed for this mutation"}, status_code=403
            )
        if (
            csrf
            and cookie_mutation
            and not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf)
        ):
            return JSONResponse(
                {"detail": "CSRF verification required"}, status_code=403
            )
    if (
        authorization is not None
        and authorization.mfa_enrollment_required
        and not (
            request.method in {"GET", "HEAD"}
            and (path in {"/", "/app"} or path.startswith(("/app/", "/themes/")))
        )
        and path
        not in {
            "/api/account",
            "/api/account/security",
            "/api/account/security/verify",
            "/api/account/security/mfa/enroll",
            "/api/account/security/mfa/confirm",
            "/auth/logout",
            "/auth/reauth",
            "/api/setup/status",
        }
    ):
        return JSONResponse(
            {
                "detail": "Administrator MFA is required. Enroll an authenticator in Account security."
            },
            status_code=403,
            headers={"X-BSM-MFA-Enrollment": "required"},
        )
    ticket = current_authorization.set(authorization)
    permission_ticket = operation_permissions.set(frozenset())
    try:
        response = await call_next(request)
        issued = getattr(request.state, "issued_session_id", None)
        if issued:
            secret = await get_jwt_secret_key(request.app.state.app_context.settings)
            csrf = hmac.new(
                secret.encode(), ("csrf:" + issued).encode(), hashlib.sha256
            ).hexdigest()
        if (
            getattr(request.state, "invalid_session", False)
            and response.status_code == 401
        ):
            response.headers["X-BSM-Session-Invalid"] = "1"
        if csrf:
            response.headers["X-BSM-CSRF-Token"] = csrf
            response.headers["Cache-Control"] = "no-store"
        if authorization is not None:
            response.headers["X-BSM-Policy-Revision"] = authorization.revision
        return response
    finally:
        current_authorization.reset(ticket)
        operation_permissions.reset(permission_ticket)
