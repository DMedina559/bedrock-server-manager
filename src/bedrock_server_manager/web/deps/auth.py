import logging
from typing import Optional, cast

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import (
    APIKeyCookie,
    HTTPBearer,
    OAuth2PasswordBearer,
    SecurityScopes,
)
from jose import jwt

from .. import auth as auth_utils
from ..access_policy import CORE_DESCRIPTIONS, policy_for
from ..schemas import UserResponse

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/token", scopes=dict(CORE_DESCRIPTIONS), auto_error=False
)
cookie_scheme = APIKeyCookie(name="access_token_cookie", auto_error=False)
integration_scheme = HTTPBearer(
    scheme_name="IntegrationToken",
    description="Named integration credential, supplied as Bearer bsm_it_...",
    auto_error=False,
)


async def get_current_user_optional(
    request: Request,
    token_bearer: Optional[str] = Depends(oauth2_scheme),
    token_cookie: Optional[str] = Depends(cookie_scheme),
    token_integration=Depends(integration_scheme),
) -> Optional[UserResponse]:
    """Resolve a user from bearer or cookie credentials, or return ``None``."""
    if getattr(request.state, "authentication_resolved", False):
        return cast(Optional[UserResponse], request.state.current_user)
    if hasattr(token_bearer, "dependency"):
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token_bearer = parts[1]
            else:
                token_bearer = None
        else:
            token_bearer = None

    if hasattr(token_cookie, "dependency"):
        token_cookie = request.cookies.get("access_token_cookie")

    # An explicit Authorization header always selects bearer authentication.
    # Invalid credentials must never select a different cookie identity.
    token: Optional[str]
    explicit = request.headers.get("Authorization")
    if explicit is not None:
        parts = explicit.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            request.state.credential_source = "bearer"
            return None
        token = parts[1]
        request.state.credential_source = "bearer"
    else:
        token = token_bearer or token_cookie
        request.state.credential_source = (
            "bearer" if token_bearer else "cookie" if token_cookie else None
        )

    if not token:
        return None

    app_context = request.app.state.app_context
    if token.startswith("bsm_it_"):
        if request.state.credential_source != "bearer":
            return None
        result = await app_context.access_service.authenticate(token)
        if result is None:
            return None
        user, authorization = result
    else:
        user = await auth_utils._get_user_from_token(app_context, token)
        request.state.invalid_session = user is None
        session_id = jwt.get_unverified_claims(token).get("sid") if user else None
        request.state.session_id = session_id
        authorization = (
            await app_context.access_service.snapshot(user, session_id=session_id)
            if user
            else None
        )
    request.state.authorization = authorization
    return user if authorization is not None else None


async def get_current_user(
    request: Request,
    user: Optional[UserResponse] = Security(get_current_user_optional),
) -> UserResponse:
    """Require an authenticated user; otherwise respond with HTTP 401."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    authorization = getattr(request.state, "authorization", None)
    if authorization is not None and authorization.restricted:
        from ..access_metadata import dependency_tree

        route = request.scope.get("route")
        permission_aware = route is not None and any(
            node.call is require_permissions
            for node in dependency_tree(route.dependant)
        )
        session_exception = authorization.token_id is None and getattr(
            getattr(route, "endpoint", None), "__bsm_assigned_session__", False
        )
        if not permission_aware and not session_exception:
            raise HTTPException(
                403, "This operation does not support restricted credentials"
            )
    return user


async def get_admin_user(current_user: UserResponse = Security(get_current_user)):
    """
    FastAPI dependency that requires the current user to be an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )
    return current_user


async def get_moderator_user(current_user: UserResponse = Security(get_current_user)):
    """
    FastAPI dependency that requires the current user to be a moderator or an admin.
    """
    if current_user.role not in ["admin", "moderator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )
    return current_user


async def require_permissions(
    request: Request,
    security_scopes: SecurityScopes,
    user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Require all declared scopes against the account's current role."""
    required = set(security_scopes.scopes)
    policy = policy_for(request)
    headers = None
    if getattr(request.state, "credential_source", None) == "bearer":
        scopes = " ".join(sorted(required))
        headers = {
            "WWW-Authenticate": f'Bearer error="insufficient_scope", scope="{scopes}"'
        }
    authorization = getattr(request.state, "authorization", None)
    if authorization is not None:
        route = request.scope.get("route")
        collection = getattr(
            getattr(route, "endpoint", None), "__bsm_server_collection__", False
        )
        server_name = request.path_params.get("server_name")
        permitted = all(
            (
                scope in authorization.permissions
                if collection
                else authorization.allows(scope, server_name)
            )
            for scope in required
        )
        if not permitted:
            raise HTTPException(
                403, "Permission denied for this credential or server", headers=headers
            )
    # Fail closed even for admin when a plugin has been unloaded.
    if not required <= policy.descriptions.keys() or not required <= policy.resolve(
        user.role
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this resource.",
            headers=headers,
        )
    if (
        authorization is not None
        and required & {"users:manage", "access:manage", "sessions:admin"}
        and request.method not in {"GET", "HEAD", "OPTIONS"}
    ):
        await request.app.state.app_context.session_service.require_recent(
            user, getattr(request.state, "session_id", None)
        )
    from ..authorization import operation_permissions

    operation_permissions.set(operation_permissions.get() | frozenset(required))
    return user
