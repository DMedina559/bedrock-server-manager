import datetime
import logging
import secrets
from datetime import timezone
from typing import Optional

import bcrypt
from fastapi import WebSocketException, status
from jose import JWTError, jwt

from ..config import Settings
from ..context import AppContext
from ..db.models import User as UserModel
from ..web.schemas import UserResponse

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


# --- JWT Configuration ---
def get_jwt_secret_key(settings: Settings) -> str:
    """Gets the JWT secret key from the database, or creates one if it doesn't exist."""
    jwt_secret_key = settings.get("web.jwt_secret_key")

    if not jwt_secret_key:
        jwt_secret_key = secrets.token_urlsafe(32)
        settings.set("web.jwt_secret_key", jwt_secret_key)
        logger.info("JWT secret key not found in settings, generating a new one")

    return str(jwt_secret_key)


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
    return str(encoded_jwt)


# --- Token Verification and User Retrieval ---


def _get_and_update_user_from_db(db_session, username: str) -> Optional[UserResponse]:
    """Helper function to fetch user, update last_seen, and return UserResponse."""
    user = db_session.query(UserModel).filter(UserModel.username == username).first()
    if not user or not user.is_active:
        return None

    user.last_seen = datetime.datetime.now(timezone.utc)
    db_session.commit()

    return UserResponse(
        id=user.id,
        username=user.username,
        identity_type="jwt",
        role=user.role,
        is_active=user.is_active,
        theme=user.theme,
    )


def _get_user_from_token(app_context: AppContext, token: str) -> Optional[UserResponse]:
    """Helper function to decode a JWT and retrieve the associated user."""
    try:
        settings = app_context.settings
        JWT_SECRET_KEY = get_jwt_secret_key(settings)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None

        with app_context.db.session_manager() as db:  # type: ignore
            return _get_and_update_user_from_db(db, username)

    except JWTError:
        return None


def authenticate_websocket_token(app_context: AppContext, token: str) -> UserResponse:
    """
    Authenticates a WebSocket connection using a provided token.

    This function extracts the user using `_get_user_from_token`.
    If the token is missing, invalid, or the user doesn't exist, it raises
    a WebSocketException to allow the router to close the connection gracefully.

    Args:
        app_context (AppContext): The application context.
        token (str): The JWT access token.

    Returns:
        UserResponse: The authenticated user object.

    Raises:
        WebSocketException: With code 1008 if authentication fails.
    """
    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing token"
        )

    user = _get_user_from_token(app_context, token)

    if user is None:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token, user not found, or inactive",
        )

    return user


# --- Utility for Login Route ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a stored hash using bcrypt.

    Args:
        plain_password (str): The plain text password to verify.
        hashed_password (str): The stored hashed password.

    Returns:
        bool: ``True`` if the password matches the hash, ``False`` otherwise.
    """
    return bool(
        bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    )


def get_password_hash(password: str) -> str:
    """Hashes a password using bcrypt.

    Args:
        password (str): The plain text password to hash.

    Returns:
        str: The hashed password.
    """
    return str(
        bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    )


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
    with app_context.db.session_manager() as db:  # type: ignore
        user = db.query(UserModel).filter(UserModel.username == username_form).first()
        if not user:
            return None
        if not verify_password(password_form, user.hashed_password):
            return None
        return str(user.username)
