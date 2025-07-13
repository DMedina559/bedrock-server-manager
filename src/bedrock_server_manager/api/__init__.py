# bedrock_server_manager/api/__init__.py
from . import addon
from . import application
from . import backup_restore
from . import info
from . import misc
from . import player
from . import plugins
from . import server
from . import server_install_config
from . import settings
from . import system
from . import task_scheduler
from . import utils
from . import web
from . import world

__all__ = [
    "application",
    "addon",
    "backup_restore",
    "info",
    "misc",
    "player",
    "plugins",
    "server",
    "server_install_config",
    "settings",
    "system",
    "task_scheduler",
    "utils",
    "web",
    "world",
]

# --- LOAD PLUGINS AND FIRE STARTUP EVENT ---
from bedrock_server_manager import plugin_manager

# Now that all APIs are registered, we can safely load the plugins.
plugin_manager.load_plugins()

# Trigger the startup event, respecting the process guard.
plugin_manager.trigger_guarded_event("on_manager_startup")
