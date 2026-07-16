"""
Web routers package.
"""

from .account import router as account_router
from .addon import router as addon_router
from .allowlist import router as allowlist_router
from .api_info import router as api_info_router
from .audit_log import router as audit_log_router
from .auth import router as auth_router
from .backup_restore import router as backup_restore_router
from .bans import router as bans_router
from .install import router as install_router
from .main import router as main_router
from .permissions import router as permissions_router
from .plugin import router as plugin_router
from .properties import router as properties_router
from .register import router as register_router
from .server_actions import router as server_actions_router
from .server_settings import router as server_settings_router
from .settings import router as settings_router
from .setup import router as setup_router
from .tasks import router as tasks_router
from .users import router as users_router
from .util import router as util_router
from .websocket import router as websocket_router
from .world import router as world_router

__all__ = [
    "account_router",
    "addon_router",
    "api_info_router",
    "audit_log_router",
    "auth_router",
    "backup_restore_router",
    "bans_router",
    "main_router",
    "plugin_router",
    "register_router",
    "server_actions_router",
    "allowlist_router",
    "permissions_router",
    "properties_router",
    "install_router",
    "server_settings_router",
    "settings_router",
    "setup_router",
    "tasks_router",
    "users_router",
    "util_router",
    "websocket_router",
    "world_router",
]
