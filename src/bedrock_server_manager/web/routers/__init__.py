# src/bedrock_server_manager/web/routers/__init__.py
"""Exports all APIRouter instances for easy inclusion in the main FastAPI app."""

from .api_info import router as api_info_router
from .auth import router as auth_router
from .backup_restore import router as backup_restore_router
from .content import router as content_router
from .main import router as main_router
from .plugin import router as plugin_router
from .server_actions import router as server_actions_router
from .server_install_config import router as server_install_config_router
from .settings import router as settings_router
from .util import router as util_router
from .server_settings import router as server_settings_router
from .tasks import router as tasks_router
from .setup import router as setup_router
from .account_router import router as account_router
from .users import router as users_router
from .register import router as register_router
from .audit_log import router as audit_log_router
from .websocket_router import router as websocket_router

__all__ = [
    "websocket_router",
    "api_info_router",
    "auth_router",
    "backup_restore_router",
    "content_router",
    "main_router",
    "plugin_router",
    "server_actions_router",
    "server_install_config_router",
    "settings_router",
    "tasks_router",
    "util_router",
    "setup_router",
    "users_router",
    "register_router",
    "audit_log_router",
]
