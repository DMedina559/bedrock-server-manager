# bedrock_server_manager/web/auth_utils.py
"""Authentication utilities for the FastAPI web application.

This module provides functions and configurations related to user authentication,
including:
- Password hashing and verification using :mod:`passlib`.
- JSON Web Token (JWT) creation, decoding, and management using :mod:`jose`.
- FastAPI security schemes (:class:`~fastapi.security.OAuth2PasswordBearer` and
  :class:`~fastapi.security.APIKeyCookie`) for token handling.
- FastAPI dependencies (:func:`~.get_current_user`, :func:`~.get_current_user_optional`)
  for protecting routes and retrieving authenticated user information.
- User authentication against credentials stored in environment variables.

The JWT secret key and token expiration are configurable via environment variables
or application settings.
"""
import os
import datetime
import logging
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from fastapi import HTTPException, Security, Request
from fastapi.security import OAuth2PasswordBearer, APIKeyCookie
from passlib.context import CryptContext

from bedrock_server_manager.config.const import env_name
from bedrock_server_manager.config.settings import settings

logger = logging.getLogger(__name__)

# --- Passlib Context ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- JWT Configuration ---
JWT_SECRET_KEY_ENV = f"{env_name}_TOKEN"
JWT_SECRET_KEY = os.environ.get(JWT_SECRET_KEY_ENV)

if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = settings.get(
        "web.jwt_secret_key", "a_very_secret_key_that_should_be_changed"
    )
    if JWT_SECRET_KEY == "a_very_secret_key_that_should_be_changed":
        logger.error(
            f"!!! SECURITY WARNING !!! Using default JWT_SECRET_KEY from settings. "
            f"Set the '{JWT_SECRET_KEY_ENV}' environment variable for production."
        )
ALGORITHM = "HS256"
try:
    JWT_EXPIRES_WEEKS = float(settings.get("web.token_expires_weeks", 4.0))
except (ValueError, TypeError):
    JWT_EXPIRES_WEEKS = 4.0
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_EXPIRES_WEEKS * 7 * 24 * 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)
cookie_scheme = APIKeyCookie(name="access_token_cookie", auto_error=False)


# --- Token Creation ---
def create_access_token(
    data: dict, expires_delta: Optional[datetime.timedelta] = None
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
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- Token Verification and User Retrieval ---
async def get_current_user_optional(
    request: Request,
    token_header: Optional[str] = Security(oauth2_scheme),
    token_cookie: Optional[str] = Security(cookie_scheme),
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency to retrieve the current user if authenticated.

    This dependency attempts to decode a JWT token (using :func:`jose.jwt.decode`)
    obtained from either the Authorization header (Bearer token via :data:`oauth2_scheme`)
    or an HTTP cookie ("access_token_cookie" via :data:`cookie_scheme`).

    If a valid token is found and successfully decoded, it returns a dictionary
    containing the username (from the "sub" claim) and an identity type.
    Otherwise, it returns ``None``.

    This is typically used for routes that can be accessed by both authenticated
    and unauthenticated users, or as a helper for other dependencies like
    :func:`~.get_current_user`.

    Args:
        request (:class:`fastapi.Request`): The incoming request object.
        token_header (Optional[str]): Token from the OAuth2PasswordBearer security scheme.
            Injected by FastAPI.
        token_cookie (Optional[str]): Token from the APIKeyCookie security scheme.
            Injected by FastAPI.

    Returns:
        Optional[Dict[str, Any]]: A dictionary ``{"username": str, "identity_type": "jwt"}``
        if authentication is successful, otherwise ``None``.
    """
    token = token_header or token_cookie
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None
        return {"username": username, "identity_type": "jwt"}
    except JWTError:
        return None


async def get_current_user(
    request: Request,
    user: Optional[Dict[str, Any]] = Security(get_current_user_optional),
) -> Dict[str, Any]:
    """
    FastAPI dependency that requires an authenticated user.

    This dependency relies on :func:`~.get_current_user_optional`. If that
    returns ``None`` (i.e., no valid token found or user not authenticated),
    this dependency raises an :class:`~fastapi.HTTPException` with a 401
    status code, prompting authentication.

    It's used to protect routes that require a logged-in user.

    Args:
        request (:class:`fastapi.Request`): The incoming request object.
        user (Optional[Dict[str, Any]]): The user data dictionary returned by
            :func:`~.get_current_user_optional`. Injected by FastAPI.

    Returns:
        Dict[str, Any]: The user data dictionary (e.g., ``{"username": str}``)
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


# --- Utility for Login Route ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a stored hash using passlib.

    Uses the global :data:`pwd_context` (a :class:`passlib.context.CryptContext` instance)
    to perform the verification.

    Args:
        plain_password (str): The plain text password to verify.
        hashed_password (str): The stored hashed password.

    Returns:
        bool: ``True`` if the password matches the hash, ``False`` otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a password using passlib (for generating new password hashes).

    Uses the global :data:`pwd_context` (a :class:`passlib.context.CryptContext` instance)
    to generate the hash.

    Args:
        password (str): The plain text password to hash.

    Returns:
        str: The generated password hash.
    """
    return pwd_context.hash(password)


def authenticate_user(username_form: str, password_form: str) -> Optional[str]:
    """
    Authenticates a user against environment variable credentials.

    This function checks the provided `username_form` and `password_form`
    against credentials stored in environment variables:
    - Username is checked against :const:`~bedrock_server_manager.config.const.env_name` + ``_USERNAME``.
    - Password is verified against a stored hash (from
      :const:`~bedrock_server_manager.config.const.env_name` + ``_PASSWORD``)
      using :func:`.verify_password`.

    Args:
        username_form (str): The username submitted by the user.
        password_form (str): The plain text password submitted by the user.

    Returns:
        Optional[str]: The username if authentication is successful,
        otherwise ``None``. Prints a critical log if environment variables
        are not set.
    """
    USERNAME_ENV = f"{env_name}_USERNAME"
    PASSWORD_ENV = f"{env_name}_PASSWORD"
    stored_username = os.environ.get(USERNAME_ENV)
    stored_password_hash = os.environ.get(PASSWORD_ENV)

    if not stored_username or not stored_password_hash:
        logger.error(
            "CRITICAL: Web authentication environment variables (USERNAME or PASSWORD HASH) are not set."
        )
        return None

    if username_form == stored_username and verify_password(
        password_form, stored_password_hash
    ):
        return stored_username
    return None
