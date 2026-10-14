import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie, OAuth2PasswordBearer
from starlette.authentication import AuthCredentials, AuthenticationBackend, SimpleUser

from ...utils import auth as auth_utils
from ..schemas import UserResponse

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)
cookie_scheme = APIKeyCookie(name="access_token_cookie", auto_error=False)


async def get_current_user_optional(
    request: Request,
    token_bearer: Optional[str] = Depends(oauth2_scheme),
    token_cookie: Optional[str] = Depends(cookie_scheme),
) -> Optional[UserResponse]:
    """Resolve a user from bearer or cookie credentials, or return ``None``."""
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

    token = token_bearer or token_cookie

    if not token:
        return None

    app_context = request.app.state.app_context
    return await auth_utils._get_user_from_token(app_context, token)


async def get_current_user(
    user: Optional[UserResponse] = Security(get_current_user_optional),
) -> UserResponse:
    """Require an authenticated user; otherwise respond with HTTP 401."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


class CustomAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if await conn.app.state.app_context.check_setup():
            return AuthCredentials(["unauthenticated"]), SimpleUser("guest")

        user = await get_current_user_optional(conn)
        if user is None:
            return

        return AuthCredentials(["authenticated"]), SimpleUser(user.username)


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
