# bedrock_server_manager/config/__init__.py
"""
The `config` package handles application configuration, settings, and constants.

This includes:
- Loading and managing user-defined settings from configuration files.
- Defining application-wide constants such as paths, names, and default values.
- Providing access to these configurations throughout the application.
"""

from .settings import Settings
from .const import (
    package_name,
    executable_name,
    app_name_title,
    env_name,
    EXPATH,
    SCRIPT_DIR,
    GUARD_VARIABLE,
    DEFAULT_ENABLED_PLUGINS,
    EVENT_IDENTITY_KEYS,
    get_installed_version,
    SERVER_TIMEOUT,
)
from .blocked_commands import API_COMMAND_BLACKLIST
from .splash_text import SPLASH_TEXTS

__all__ = [
    # from settings.py
    "Settings",
    # from const.py
    "package_name",
    "executable_name",
    "app_name_title",
    "env_name",
    "EXPATH",
    "SCRIPT_DIR",
    "GUARD_VARIABLE",
    "DEFAULT_ENABLED_PLUGINS",
    "EVENT_IDENTITY_KEYS",
    "get_installed_version",
    "SERVER_TIMEOUT",
    # from blocked_commands.py
    "API_COMMAND_BLACKLIST",
    # from splash_text.py
    "SPLASH_TEXTS",
]
