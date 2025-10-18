# bedrock_server_manager/web/auth_utils.py
"""Authentication utilities for the FastAPI web application.

This module provides functions and configurations related to user authentication,
including:
- Password hashing and verification using :mod:`bcrypt`.
- JSON Web Token (JWT) creation, decoding, and management using :mod:`jose`.
- FastAPI security schemes (:class:`~fastapi.security.OAuth2PasswordBearer` and
  :class:`~fastapi.security.APIKeyCookie`) for token handling.
- FastAPI dependencies (:func:`~.get_current_user`, :func:`~.get_current_user_optional`)
  for protecting routes and retrieving authenticated user information.
- User authentication against credentials stored in environment variables.

The JWT secret key and token expiration are configurable via environment variables.
"""
import datetime
from datetime import timezone
import logging
from typing import Optional, Dict, Any
import secrets

import bcrypt
from jose import JWTError, jwt
from fastapi import (
    HTTPException,
    Security,
    Request,
    status,
    WebSocket,
    WebSocketException,
)
from fastapi.security import OAuth2PasswordBearer, APIKeyCookie
from starlette.authentication import AuthCredentials, AuthenticationBackend, SimpleUser

from ..error import MissingArgumentError
from .schemas import User
from ..db.models import User as UserModel
from ..context import AppContext
from ..config import Settings

logger = logging.getLogger(__name__)


# --- JWT Configuration ---
def get_jwt_secret_key(settings: Settings) -> str:
    """Gets the JWT secret key from the database, or creates one if it doesn't exist."""
    jwt_secret_key = settings.get("web.jwt_secret_key")

    if not jwt_secret_key:
        jwt_secret_key = secrets.token_urlsafe(32)
        settings.set("web.jwt_secret_key", jwt_secret_key)
        logger.info("JWT secret key not found in settings, generating a new one")

    return jwt_secret_key


ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)
cookie_scheme = APIKeyCookie(name="access_token_cookie", auto_error=False)


# --- Token Creation ---
def create_access_token(
    app_context: AppContext,
    data: dict,
    expires_delta: Optional[datetime.timedelta] = None,
) -> str:
    """Creates a JSON Web Token (JWT) for access.

    The token includes the provided `data` (typically user identifier) and
    an expiration time. Uses :func:`jose.jwt.encode`.

    Args:
        data (dict): The data to encode in the token (e.g., ``{"sub": username}``).
        expires_delta (Optional[datetime.timedelta], optional): The lifespan
            of the token. If ``None``, defaults to the duration specified by
            the global ``ACCESS_TOKEN_EXPIRE_MINUTES``. Defaults to ``None``.

    Returns:
        str: The encoded JWT string.
    """
    to_encode = data.copy()

    settings = app_context.settings

    JWT_SECRET_KEY = get_jwt_secret_key(settings)

    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        try:
            jwt_expires_weeks = float(settings.get("web.token_expires_weeks", 4.0))
        except (ValueError, TypeError):
            jwt_expires_weeks = 4.0
        access_token_expire_minutes = jwt_expires_weeks * 7 * 24 * 60
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- Token Verification and User Retrieval ---
async def get_current_user_optional(
    request: Request,
) -> Optional[User]:
    """
    FastAPI dependency to retrieve the current user if authenticated.

    This dependency attempts to decode a JWT token (using :func:`jose.jwt.decode`)
    obtained from either the Authorization header (Bearer token) or an HTTP
    cookie ("access_token_cookie").

    If a valid token is found and successfully decoded, it returns a dictionary
    containing the username (from the "sub" claim) and an identity type.
    Otherwise, it returns ``None``.

    This is typically used for routes that can be accessed by both authenticated
    and unauthenticated users, or as a helper for other dependencies like
    :func:`~.get_current_user`.

    Args:
        request (:class:`fastapi.Request`): The incoming request object.

    Returns:
        Optional[User]: A dictionary ``{"username": str, "identity_type": "jwt"}``
        if authentication is successful, otherwise ``None``.
    """
    token = request.cookies.get("access_token_cookie")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]

    if not token:
        return None

    try:
        app_context = request.app.state.app_context
        settings = app_context.settings
        JWT_SECRET_KEY = get_jwt_secret_key(settings)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None

        def get_user_from_db(db_session):
            user = (
                db_session.query(UserModel)
                .filter(UserModel.username == username)
                .first()
            )
            if not user or not user.is_active:
                return None

            user.last_seen = datetime.datetime.now(timezone.utc)
            db_session.commit()

            return User(
                id=user.id,
                username=user.username,
                identity_type="jwt",
                role=user.role,
                is_active=user.is_active,
                theme=user.theme,
            )

        with app_context.db.session_manager() as db:
            return get_user_from_db(db)

    except JWTError:
        return None


async def get_current_user(
    user: Optional[User] = Security(get_current_user_optional),
) -> User:
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


async def get_current_user_for_websocket(
    websocket: WebSocket,
) -> User:
    """
    FastAPI dependency for authenticating WebSocket connections.

    This dependency extracts a JWT token from the 'token' query parameter
    of a WebSocket connection URL. It decodes the token and retrieves the
    corresponding user from the database.

    If the token is missing, invalid, or the user doesn't exist, it raises
    a WebSocketException to close the connection gracefully.

    Args:
        websocket (WebSocket): The WebSocket connection object.

    Returns:
        User: The authenticated user object.

    Raises:
        WebSocketException: With code 1008 if authentication fails.
    """
    token = websocket.query_params.get("token")
    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing token"
        )

    try:
        app_context = websocket.app.state.app_context
        settings = app_context.settings
        JWT_SECRET_KEY = get_jwt_secret_key(settings)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload"
            )

        def get_user_from_db(db_session):
            user = (
                db_session.query(UserModel)
                .filter(UserModel.username == username)
                .first()
            )
            if not user or not user.is_active:
                return None

            user.last_seen = datetime.datetime.now(timezone.utc)
            db_session.commit()

            return User(
                id=user.id,
                username=user.username,
                identity_type="jwt",
                role=user.role,
                is_active=user.is_active,
                theme=user.theme,
            )

        with app_context.db.session_manager() as db:
            user = get_user_from_db(db)
            if user is None:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="User not found or inactive",
                )
            return user

    except JWTError:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
        )


# --- Utility for Login Route ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a stored hash using bcrypt.

    Args:
        plain_password (str): The plain text password to verify.
        hashed_password (str): The stored hashed password.

    Returns:
        bool: ``True`` if the password matches the hash, ``False`` otherwise.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Hashes a password using bcrypt.

    Args:
        password (str): The plain text password to hash.

    Returns:
        str: The hashed password.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


from ..config import bcm_config


class CustomAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if bcm_config.needs_setup(conn.app.state.app_context):
            return AuthCredentials(["unauthenticated"]), SimpleUser("guest")

        user = await get_current_user_optional(conn)
        if user is None:
            return

        return AuthCredentials(["authenticated"]), SimpleUser(user.username)


def authenticate_user(
    app_context: AppContext, username_form: str, password_form: str
) -> Optional[str]:
    """
    Authenticates a user against the database.

    This function checks the provided `username_form` and `password_form`
    against credentials stored in the database.

    Args:
        username_form (str): The username submitted by the user.
        password_form (str): The plain text password submitted by the user.

    Returns:
        Optional[str]: The username if authentication is successful,
        otherwise ``None``.
    """
    with app_context.db.session_manager() as db:
        user = db.query(UserModel).filter(UserModel.username == username_form).first()
        if not user:
            return None
        if not verify_password(password_form, user.hashed_password):
            return None
        return user.username


async def get_admin_user(current_user: User = Security(get_current_user)):
    """
    FastAPI dependency that requires the current user to be an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )
    return current_user


async def get_moderator_user(current_user: User = Security(get_current_user)):
    """
    FastAPI dependency that requires the current user to be a moderator or an admin.
    """
    if current_user.role not in ["admin", "moderator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )
    return current_user
