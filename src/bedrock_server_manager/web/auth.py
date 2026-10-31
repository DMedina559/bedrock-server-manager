from __future__ import annotations

import asyncio
import datetime
import logging
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
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
from ..utils.threads import run_in_thread
from .authorization import Authorization
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


def token_lifetime(settings, *, remember_me=True) -> datetime.timedelta:
    """Pure lifetime policy shared by login, renewal and direct token creation.

    Persisted session limits remain authoritative when the token is issued.
    """
    if not remember_me:
        return datetime.timedelta(hours=24)
    try:
        weeks = float(settings.get("web.token_expires_weeks", 4.0))
        if not 0 < weeks <= 5200:
            raise ValueError("Invalid token lifetime")
        return datetime.timedelta(weeks=weeks)
    except (TypeError, ValueError, OverflowError):
        return datetime.timedelta(weeks=4)


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

    expire = datetime.datetime.now(datetime.timezone.utc) + (
        expires_delta if expires_delta is not None else token_lifetime(settings)
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


@dataclass(frozen=True)
class AuthenticatedSession:
    """Server-created identity and authorization for one authentication operation."""

    user: UserResponse
    authorization: Authorization


async def resolve_session_token(
    app_context: AppContext, token: str
) -> Optional[AuthenticatedSession]:
    """Resolve a JWT against persisted identity, session and current grants once.

    The result belongs to this request/handshake; it is never cached across requests.
    """
    try:
        secret = await get_jwt_secret_key(app_context.settings)
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        username = payload.get("sub")
        owner_id = payload.get("aid")
        if not isinstance(username, str) or not isinstance(owner_id, str):
            return None
        async with app_context.storage.transaction() as session:
            owner = await app_context.storage.user_repo.get_user_by_username(
                session, username
            )
            if owner is None or not owner.is_active or owner.access_id != owner_id:
                return None
            user = UserResponse.model_validate(
                {
                    "id": owner.id,
                    "username": owner.username,
                    "identity_type": "jwt",
                    "role": owner.role,
                    "is_active": owner.is_active,
                    "theme": owner.theme,
                }
            )
        validated = await app_context.session_service.validate(
            payload.get("sid"), owner_id
        )
        if validated is None:
            return None
        authorization = await app_context.access_service._snapshot(
            user, session_id=validated.id, validated_session=validated
        )
        return (
            AuthenticatedSession(user, authorization)
            if authorization is not None
            else None
        )
    except JWTError:
        return None
    except Exception as error:
        from ..error import DependencyUnavailableError

        if isinstance(error, DependencyUnavailableError):
            raise
        raise DependencyUnavailableError(
            "Authentication infrastructure is unavailable."
        ) from error


async def _get_user_from_token(
    app_context: AppContext, token: str
) -> Optional[UserResponse]:
    identity = await resolve_session_token(app_context, token)
    return identity.user if identity is not None else None


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
