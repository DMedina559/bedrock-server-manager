# bedrock_server_manager/web/__init__.py
from .app import run_web_server
from .tasks import create_task, update_task, get_task, run_task
from .templating import get_templates
from .auth_utils import (
    pwd_context,
    create_access_token,
    get_current_user_optional,
    get_current_user,
    verify_password,
    authenticate_user,
    oauth2_scheme,
    cookie_scheme,
)
from .dependencies import validate_server_exists

__all__ = [
    "run_web_server",
    # Tasks
    "create_task",
    "update_task",
    "get_task",
    "run_task",
    # Templating
    "get_templates",
    # Auth utils
    "pwd_context",
    "create_access_token",
    "get_current_user_optional",
    "get_current_user",
    "verify_password",
    "authenticate_user",
    "oauth2_scheme",
    "cookie_scheme",
    # Dependencies
    "validate_server_exists",
]
