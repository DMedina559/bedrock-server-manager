import datetime
import logging
import secrets
from datetime import timezone
from typing import Any, Optional

import bcrypt
from fastapi import WebSocketException, status
from jose import JWTError, jwt

from ..config import Settings
from ..context import AppContext
from ..web.schemas import UserResponse

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


# --- JWT Configuration ---
async def get_jwt_secret_key(settings: Settings) -> str:
    """Gets the JWT secret key from the database, or creates one if it doesn't exist."""
    jwt_secret_key = settings.get("web.jwt_secret_key")

    if not jwt_secret_key:
        jwt_secret_key = secrets.token_urlsafe(32)
        await settings.set("web.jwt_secret_key", jwt_secret_key)
        logger.info("JWT secret key not found in settings, generating a new one")

    return str(jwt_secret_key)


# --- Token Creation ---
async def create_access_token(
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

    JWT_SECRET_KEY = await get_jwt_secret_key(settings)

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


async def _get_and_update_user_from_db(
    app_context: AppContext, session, username: str
) -> Optional[UserResponse]:
    """Helper function to fetch user via UserRepository, update last_seen, and return UserResponse."""
    user: Any = await app_context.storage.user_repo.get_user_by_username(
        session, username
    )
    if not user or not user.is_active:
        return None

    now = datetime.datetime.now(timezone.utc)

    # SQLite often returns naive datetime objects.
    # Make sure we compare aware-to-aware datetimes.
    last_seen_dt = user.last_seen
    if last_seen_dt is not None and last_seen_dt.tzinfo is None:
        last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)

    # Only update the database if last_seen is missing or older than 5 minutes
    if last_seen_dt is None or (now - last_seen_dt) > datetime.timedelta(minutes=5):
        user.last_seen = now

    return UserResponse(
        id=int(user.id),
        username=str(user.username),
        identity_type="jwt",
        role=str(user.role),
        is_active=bool(user.is_active),
        theme=str(user.theme),
    )


async def _get_user_from_token(
    app_context: AppContext, token: str
) -> Optional[UserResponse]:
    """Helper function to decode a JWT and retrieve the associated user."""
    try:
        settings = app_context.settings
        JWT_SECRET_KEY = await get_jwt_secret_key(settings)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None

        async with app_context.storage.transaction() as session:
            return await _get_and_update_user_from_db(app_context, session, username)

    except JWTError:
        return None


async def authenticate_websocket_token(
    app_context: AppContext, token: str
) -> UserResponse:
    """Authenticates a WebSocket connection using a provided token."""
    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing token"
        )

    user = await _get_user_from_token(app_context, token)

    if user is None:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token, user not found, or inactive",
        )

    return user


# --- Utility for Login Route ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a stored hash using bcrypt."""
    return bool(
        bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    )


def get_password_hash(password: str) -> str:
    """Hashes a password using bcrypt."""
    return str(
        bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    )


async def authenticate_user(
    app_context: AppContext, username_form: str, password_form: str
) -> Optional[str]:
    """Authenticates a user against the database using UserRepository."""
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.get_user_by_username(
            session, username_form
        )
        if not user:
            return None
        if not verify_password(password_form, str(user.hashed_password)):
            return None
        return str(user.username)
