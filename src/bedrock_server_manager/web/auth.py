from __future__ import annotations

import asyncio
import datetime
import logging
import secrets
from datetime import timezone
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4
from weakref import WeakValueDictionary

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, WebSocketException, status
from jose import JWTError, jwt
from pydantic import TypeAdapter

from ..config import Settings
from ..contracts import Password
from ..state.models import UserInfoState
from ..utils.threads import run_in_thread
from .schemas import UserResponse

if TYPE_CHECKING:
    from ..context import AppContext

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


# --- JWT Configuration ---
_jwt_key_lock = asyncio.Lock()


async def get_jwt_secret_key(settings: Settings) -> str:
    """Return the JWT secret key from the database, or creates one if it doesn't exist."""
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
    """Encode a JWT with a user payload and UTC expiration.

    An omitted lifetime uses ``web.token_expires_weeks`` from application settings.
    """
    to_encode = data.copy()
    if isinstance(to_encode.get("sub"), str):
        async with app_context.storage.transaction() as session:
            owner = await app_context.storage.user_repo.get_user_by_username(
                session, to_encode["sub"]
            )
            if owner is not None:
                if "authv" in to_encode and to_encode["authv"] != owner.auth_revision:
                    raise HTTPException(
                        401, "Account credentials changed; sign in again"
                    )
                to_encode["authv"] = owner.auth_revision
                to_encode["aid"] = owner.access_id

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
    owner_id = to_encode.get("aid")
    if owner_id:
        identifier = to_encode.get("sid")
        if identifier:
            login_session = await app_context.session_service.validate(
                identifier, owner_id
            )
            if login_session is None:
                raise HTTPException(401, "Session expired or revoked")
            absolute_expiry = login_session.expires_at
        else:
            identifier, absolute_expiry = await app_context.session_service.create(
                owner_id,
                int(expire.timestamp()),
                expected_revision=to_encode.get("authv"),
            )
        to_encode["sid"] = identifier
        expire = datetime.datetime.fromtimestamp(
            min(int(expire.timestamp()), absolute_expiry), datetime.timezone.utc
        )
    to_encode.update(
        {
            "exp": expire,
            "iat": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            "jti": uuid4().hex,
        }
    )
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

    return UserResponse.model_validate(
        {
            "id": int(user.id),
            "username": str(user.username),
            "identity_type": "jwt",
            "role": user.role,
            "is_active": bool(user.is_active),
            "theme": str(user.theme),
        }
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
        if payload.get("aid") is not None and username:
            async with app_context.storage.transaction() as session:
                owner = await app_context.storage.user_repo.get_user_by_username(
                    session, username
                )
                if owner is None or owner.access_id != payload["aid"]:
                    return None
        if (
            not payload.get("aid")
            or await app_context.session_service.validate(
                payload.get("sid"), payload.get("aid")
            )
            is None
        ):
            return None
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
                "Failed DB fallback lookup for user '%s': %s",
                username,
                db_err,
                exc_info=True,
            )
            from ..error import DependencyUnavailableError

            raise DependencyUnavailableError(
                "Authentication storage is unavailable."
            ) from db_err

    except JWTError:
        return None
    except Exception as e:
        from ..error import DependencyUnavailableError

        if isinstance(e, DependencyUnavailableError):
            raise
        raise DependencyUnavailableError(
            "Authentication infrastructure is unavailable."
        ) from e


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
_password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
# A fixed dummy hash avoids skipping expensive verification for unknown users.
_DUMMY_PASSWORD_HASH = "$argon2id$v=19$m=19456,t=2,p=1$c3RhdGljLWR1bW15LXNhbHQ$h9t+HjrRn7ofQei1gZsV3GTYM1A82KheDKJ3jlOXmI4"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify Argon2id credentials and existing bcrypt hashes without truncation."""
    try:
        if hashed_password.startswith("$argon2"):
            return bool(_password_hasher.verify(hashed_password, plain_password))
        if len(plain_password.encode("utf-8")) > 72:
            _password_hasher.verify(_DUMMY_PASSWORD_HASH, plain_password)
            return False
        return bool(
            bcrypt.checkpw(
                plain_password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        )
    except (VerificationError, InvalidHashError, ValueError):
        return False


def get_password_hash(password: str) -> str:
    """Hash new credentials with bounded-memory Argon2id."""
    return str(_password_hasher.hash(password))


_password_slots: WeakValueDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    WeakValueDictionary()
)


def _password_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    slots = _password_slots.get(loop)
    if slots is None:
        slots = asyncio.Semaphore(4)
        _password_slots[loop] = slots
    return slots


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Verify a password without blocking the event loop or flooding workers."""
    async with _password_semaphore():
        return await run_in_thread(verify_password, plain_password, hashed_password)


async def get_password_hash_async(password: str) -> str:
    """Hash a password with bounded, cancellation-owned worker execution."""
    async with _password_semaphore():
        return await run_in_thread(get_password_hash, password)


async def authenticate_user(
    app_context: AppContext, username_form: str, password_form: str
) -> Optional[str]:
    """Authenticates a user against the database using UserRepository."""
    password_form = (
        TypeAdapter(Password).validate_python(password_form).get_secret_value()
    )
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.get_user_by_username(
            session, username_form
        )
        hashed_password = str(user.hashed_password) if user else _DUMMY_PASSWORD_HASH
        username = str(user.username) if user else None
        owner_id = user.id if user else None
    valid = await verify_password_async(password_form, hashed_password)
    if not valid or username is None:
        return None
    if not hashed_password.startswith(
        "$argon2id$"
    ) or _password_hasher.check_needs_rehash(hashed_password):
        from sqlalchemy import update

        from ..db.models import User

        upgraded = await get_password_hash_async(password_form)
        async with app_context.storage.transaction() as session:
            await session.execute(
                update(User)
                .where(User.id == owner_id, User.hashed_password == hashed_password)
                .values(hashed_password=upgraded)
            )
    return username
