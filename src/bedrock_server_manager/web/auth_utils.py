# bedrock_server_manager/web/auth_utils.py
import os
import datetime
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from fastapi import HTTPException, Security, Request
from fastapi.security import OAuth2PasswordBearer, APIKeyCookie
from passlib.context import CryptContext

from bedrock_server_manager.config.const import env_name
from bedrock_server_manager.config.settings import settings

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
        print(
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
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# --- Utility for Login Route ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a stored hash using passlib."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a password using passlib (for generating new hashes)."""
    return pwd_context.hash(password)


def authenticate_user(username_form: str, password_form: str) -> Optional[str]:
    """
    Authenticates a user against environment variable credentials.
    Checks the provided password against a stored passlib-compatible hash.
    Returns the username if successful, None otherwise.
    """
    USERNAME_ENV = f"{env_name}_USERNAME"
    PASSWORD_ENV = f"{env_name}_PASSWORD"
    stored_username = os.environ.get(USERNAME_ENV)
    stored_password_hash = os.environ.get(PASSWORD_ENV)

    if not stored_username or not stored_password_hash:
        print(
            "CRITICAL: Web authentication environment variables (USERNAME or PASSWORD HASH) are not set."
        )
        return None

    if username_form == stored_username and verify_password(
        password_form, stored_password_hash
    ):
        return stored_username
    return None
