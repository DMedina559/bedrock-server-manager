import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie, OAuth2PasswordBearer
from starlette.authentication import AuthCredentials, AuthenticationBackend, SimpleUser

from ...config import bcm_config
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
    """
    FastAPI dependency to retrieve the current user if authenticated.

    This dependency attempts to decode a JWT token (using :func:`jose.jwt.decode`)
    obtained from the Authorization header (Bearer token).

    If a valid token is found and successfully decoded, it returns a UserResponse.
    Otherwise, it returns ``None``.

    This is typically used for routes that can be accessed by both authenticated
    and unauthenticated users, or as a helper for other dependencies like
    :func:`~.get_current_user`.

    Args:
        request (:class:`fastapi.Request`): The incoming request object.

    Returns:
        Optional[UserResponse]: The user object if authentication is successful,
        otherwise ``None``.
    """
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
    return auth_utils._get_user_from_token(app_context, token)


async def get_current_user(
    user: Optional[UserResponse] = Security(get_current_user_optional),
) -> UserResponse:
    """
    FastAPI dependency that requires an authenticated user.

    This dependency relies on :func:`~.get_current_user_optional`. If that
    returns ``None`` (i.e., no valid token found or user not authenticated),
    this dependency raises an :class:`~fastapi.HTTPException` with a 401
    status code, prompting authentication.

    It's used to protect routes that require a logged-in user.

    Args:
        request (:class:`fastapi.Request`): The incoming request object.
        user (Optional[User]): The user data dictionary returned by
            :func:`~.get_current_user_optional`. Injected by FastAPI.

    Returns:
        User: The user data dictionary (e.g., ``{"username": str}``)
        if the user is authenticated.

    Raises:
        fastapi.HTTPException: With status code 401 if the user is not authenticated.
    """
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


class CustomAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if bcm_config.needs_setup(conn.app.state.app_context):
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
