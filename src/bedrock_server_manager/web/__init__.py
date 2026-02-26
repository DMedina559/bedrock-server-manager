# bedrock_server_manager/web/__init__.py
from .auth_utils import (
    authenticate_user,
    cookie_scheme,
    create_access_token,
    get_admin_user,
    get_current_user,
    get_current_user_optional,
    get_moderator_user,
    oauth2_scheme,
    verify_password,
)
from .dependencies import get_app_context, get_templates, validate_server_exists

__all__ = [
    # Auth utils
    "create_access_token",
    "get_current_user_optional",
    "get_current_user",
    "get_moderator_user",
    "get_admin_user",
    "verify_password",
    "authenticate_user",
    "oauth2_scheme",
    "cookie_scheme",
    # Dependencies
    "validate_server_exists",
    "get_templates",
    "get_app_context",
]
