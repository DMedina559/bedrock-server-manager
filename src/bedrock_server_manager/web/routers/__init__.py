"""
Web routers package.
"""

from . import account as account_router
from . import addon as addon_router
from . import api_info as api_info_router
from . import audit_log as audit_log_router
from . import auth as auth_router
from . import backup_restore as backup_restore_router
from . import bans as bans_router
from . import main as main_router
from . import plugin as plugin_router
from . import register as register_router
from . import server_actions as server_actions_router
from . import server_install_config as server_install_config_router
from . import server_settings as server_settings_router
from . import settings as settings_router
from . import setup as setup_router
from . import spa as spa_router
from . import tasks as tasks_router
from . import users as users_router
from . import util as util_router
from . import websocket_router as websocket_router
from . import world as world_router

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
    "server_install_config_router",
    "server_settings_router",
    "settings_router",
    "setup_router",
    "spa_router",
    "tasks_router",
    "users_router",
    "util_router",
    "websocket_router",
    "world_router",
]
