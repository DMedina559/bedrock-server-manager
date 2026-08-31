# bedrock_server_manager/config/const.py
"""
Defines application-wide constants and utility functions for accessing them.

This module centralizes common identifiers, names, paths, and version information
used throughout the Bedrock Server Manager application.
"""

import os
from importlib.metadata import PackageNotFoundError, version

# --- Package Constants ---
package_name: str = "bedrock-server-manager"
"""The official package name on PyPI."""

app_author: str = "bedrock-server-manager"
"""The author name used by `platformdirs` to construct config paths."""

executable_name: str = package_name
"""The name of the main executable script for the application."""

app_module_name: str = package_name.replace("-", "_")
"""A user-friendly, snake_case version of the application name."""

app_name_title: str = package_name.replace("-", " ").title()
"""A user-friendly, title-cased version of the application name."""

env_name: str = "BSM"
"""The prefix used for environment variables related to this application (e.g., BSM_DB_URL)."""

# --- Package Information ---

APP_DIR: str = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
"""The root directory of the application."""

CONFIG_FILE_NAME = f"{app_module_name}.json"

GUARD_VARIABLE = "BSM_PLUGIN_RECURSION_GUARD"

# --- Application Constants ---
SERVER_TIMEOUT = 30

# --- PLUGIN Constants ---

# A list of plugin names (module names without .py) that are enabled by default
# when they are first discovered. Users can subsequently disable them.
DEFAULT_ENABLED_PLUGINS = [
    "auto_reload_config",
    "update_before_start",
    "server_lifecycle_notifications",
    "world_operation_notifications",
    "autostart_plugin",
]

# Placeholder for missing identifying keyword arguments
_MISSING_PARAM_PLACEHOLDER = "<PARAM_UNSPECIFIED>"


# --- Version Information ---
def get_installed_version() -> str:
    """
    Retrieves the installed version of the application package.

    Uses `importlib.metadata.version` to get the version. If the package
    is not found (e.g., in a development environment without installation),
    it defaults to "0.0.0".

    Returns:
        The installed package version string, or "0.0.0" if not found.
    """
    try:
        installed_version = version(package_name)
        return installed_version
    except PackageNotFoundError:
        installed_version = "0.0.0"
        return installed_version


# --- Web Service Constants ---
_clean_package_name_for_systemd = (
    package_name.lower().replace("_", "-").replace(" ", "-")
)
WEB_SERVICE_SYSTEMD_NAME: str = f"{_clean_package_name_for_systemd}-webui.service"
"""Name for the Web UI systemd service."""

_clean_app_title_for_windows = "".join(c for c in app_name_title if c.isalnum())
if not _clean_app_title_for_windows:
    _clean_app_title_for_windows = "AppWebUI"
WEB_SERVICE_WINDOWS_NAME_INTERNAL: str = f"{_clean_app_title_for_windows}WebUI"
"""Internal name for the Web UI Windows service."""

WEB_SERVICE_WINDOWS_DISPLAY_NAME: str = f"{app_name_title} Web UI"
"""Display name for the Web UI Windows service."""
