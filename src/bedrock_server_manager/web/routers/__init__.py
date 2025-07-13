# src/bedrock_server_manager/web/routers/__init__.py
"""Exports all APIRouter instances for easy inclusion in the main FastAPI app."""

from .api_info import router as api_info_router
from .auth import router as auth_router
from .backup_restore import router as backup_restore_router
from .content import router as content_router
from .main import router as main_router
from .plugin import router as plugin_router
from .schedule_tasks import router as schedule_tasks_router
from .server_actions import router as server_actions_router
from .server_install_config import router as server_install_config_router
from .settings import router as settings_router
from .util import router as util_router

__all__ = [
    "api_info_router",
    "auth_router",
    "backup_restore_router",
    "content_router",
    "main_router",
    "plugin_router",
    "schedule_tasks_router",
    "server_actions_router",
    "server_install_config_router",
    "settings_router",
    "util_router",
]
