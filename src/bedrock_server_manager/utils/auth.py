import asyncio
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
from ..state.models import UserInfoState
from ..web.schemas import UserResponse

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


# --- JWT Configuration ---
_jwt_key_lock = asyncio.Lock()


async def get_jwt_secret_key(settings: Settings) -> str:
    """Gets the JWT secret key from the database, or creates one if it doesn't exist."""
    jwt_secret_key = settings.get("web.jwt_secret_key")

    if not jwt_secret_key:
        async with _jwt_key_lock:
            # Re-check inside lock
            jwt_secret_key = settings.get("web.jwt_secret_key")
            if not jwt_secret_key:
                jwt_secret_key = secrets.token_urlsafe(32)
                await settings.set("web.jwt_secret_key", jwt_secret_key)
                logger.info(
                    "JWT secret key not found in settings, generating a new one"
                )

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

        # 1. Check in-memory AppState first (fast, non-blocking, avoids DB lock contention)
        u_info = app_context.state.users.get(username)
        if u_info is not None:
            if not u_info.is_active:
                return None
            return UserResponse(
                id=u_info.id or 0,
                username=u_info.username,
                identity_type="jwt",
                role=u_info.role,
                is_active=u_info.is_active,
                theme=u_info.theme,
            )

        # 2. Fall back to database query if user not found in AppState
        try:
            async with app_context.storage.write_lock:
                async with app_context.state.users.get_lock(username):
                    # A committed account mutation may have populated the cache
                    # while this lookup was waiting for the shared write lock.
                    cached = app_context.state.users.get(username)
                    if cached is not None:
                        if not cached.is_active:
                            return None
                        return UserResponse.model_validate(
                            {
                                "id": cached.id or 0,
                                "username": cached.username,
                                "identity_type": "jwt",
                                "role": cached.role,
                                "is_active": cached.is_active,
                                "theme": cached.theme,
                            }
                        )
                    async with app_context.storage.transaction() as session:
                        user_resp = await _get_and_update_user_from_db(
                            app_context, session, username
                        )
                        if user_resp is None:
                            return None
                        user = await app_context.storage.user_repo.get_user_by_username(
                            session, username
                        )
                        u_state = UserInfoState.model_validate(
                            user, from_attributes=True
                        )
                    # Preserve the complete profile and publish after last_seen commits.
                    app_context.state.users.set(u_state)
                    app_context.state.users.remove_dirty_user(username)
                    return user_resp
        except Exception as db_err:
            logger.warning(
                "Failed DB fallback lookup for user '%s': %s", username, db_err
            )
            return None

    except JWTError:
        return None
    except Exception as e:
        logger.warning("Error during user token authentication: %s", e)
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
