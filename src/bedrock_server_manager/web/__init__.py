# bedrock_server_manager/web/__init__.py
from .dependencies import validate_server_exists, get_templates, get_app_context
from .auth_utils import (
    create_access_token,
    get_current_user_optional,
    get_current_user,
    get_moderator_user,
    get_admin_user,
    verify_password,
    authenticate_user,
    oauth2_scheme,
    cookie_scheme,
)

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
