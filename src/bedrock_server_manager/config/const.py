# bedrock_server_manager/config/const.py
"""
Defines application-wide constants and utility functions for accessing them.

This module centralizes common identifiers, names, paths, and version information
used throughout the Bedrock Server Manager application.
"""
import os
from typing import Dict, Tuple
from importlib.metadata import version, PackageNotFoundError

# Local imports
from ..utils import package_finder

# --- Package Constants ---
package_name: str = "bedrock-server-manager"
"""The official package name on PyPI."""

app_author: str = "bedrock-server-manager"
"""The author name used by `appdirs` to construct config paths."""

executable_name: str = package_name
"""The name of the main executable script for the application."""

app_name_title: str = package_name.replace("-", " ").title()
"""A user-friendly, title-cased version of the application name."""

env_name: str = package_name.replace("-", "_").upper()
"""The prefix used for environment variables related to this application (e.g., BSM_PASSWORD)."""

# --- Package Information ---
EXPATH: str = package_finder.find_executable(package_name, executable_name)
"""The discovered absolute path to the main application executable."""

SCRIPT_DIR: str = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
"""The root directory of the application scripts (typically the `src` directory)."""

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

# Define which keyword arguments identify a unique instance of a standard event.
# This map is crucial for the granular re-entrancy guard in `trigger_event`.
# Format: { "event_name": ("kwarg1_name", "kwarg2_name", ...), ... }
# The order of kwarg names in the tuple matters for the generated key's consistency.
# An empty tuple means the event name itself is the unique key.
EVENT_IDENTITY_KEYS: Dict[str, Tuple[str, ...]] = {
    "before_server_start": ("server_name",),
    "after_server_start": ("server_name",),
    "before_server_stop": ("server_name",),
    "after_server_stop": ("server_name",),
    "before_command_send": ("server_name", "command"),
    "after_command_send": ("server_name", "command"),
    "before_backup": ("server_name", "backup_type"),
    "after_backup": ("server_name", "backup_type"),
    "before_restore": ("server_name", "restore_type"),
    "after_restore": ("server_name", "restore_type"),
    "before_prune_backups": ("server_name",),
    "after_prune_backups": ("server_name",),
    "before_allowlist_change": ("server_name",),
    "after_allowlist_change": ("server_name",),
    "before_permission_change": ("server_name", "xuid"),
    "after_permission_change": ("server_name", "xuid"),
    "before_properties_change": ("server_name",),
    "after_properties_change": ("server_name",),
    "before_server_install": ("server_name", "target_version"),
    "after_server_install": ("server_name",),
    "before_server_update": ("server_name", "target_version"),
    "after_server_update": ("server_name",),
    "before_players_add": (),
    "after_players_add": (),
    "before_player_db_scan": (),
    "after_player_db_scan": (),
    "before_world_export": ("server_name", "export_dir"),
    "after_world_export": ("server_name",),
    "before_world_import": ("server_name", "file_path"),
    "after_world_import": ("server_name",),
    "before_world_reset": ("server_name",),
    "after_world_reset": ("server_name",),
    "before_addon_import": ("server_name", "addon_file_path"),
    "after_addon_import": ("server_name",),
    "before_service_change": ("server_name", "action"),
    "after_service_change": ("server_name", "action"),
    "before_autoupdate_change": ("server_name", "new_value"),
    "after_autoupdate_change": ("server_name",),
    "before_prune_download_cache": ("download_dir", "keep_count"),
    "after_prune_download_cache": (),
    "on_load": ("target_plugin_name",),  # For trigger_event if used for on_load
    "on_unload": ("target_plugin_name",),  # For trigger_event if used for on_unload
    "on_manager_startup": (),
    "before_web_server_start": ("mode",),
    "after_web_server_start": (),
    "before_web_server_stop": (),
    "after_web_server_stop": (),
}
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
