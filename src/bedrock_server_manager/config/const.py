# bedrock_server_manager/config/const.py
"""
Defines application-wide constants and utility functions for accessing them.

This module centralizes common identifiers, names, paths, and version information
used throughout the Bedrock Server Manager application.
"""

import os
from importlib.metadata import PackageNotFoundError, version
from typing import Dict, Tuple

# --- Package Constants ---
package_name: str = "bedrock-server-manager"
"""The official package name on PyPI."""

app_author: str = "bedrock-server-manager"
"""The author name used by `platformdirs` to construct config paths."""

executable_name: str = package_name
"""The name of the main executable script for the application."""

app_name_title: str = package_name.replace("-", " ").title()
"""A user-friendly, title-cased version of the application name."""

env_name: str = "BSM"
"""The prefix used for environment variables related to this application (e.g., BSM_PASSWORD)."""

# --- Package Information ---

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
    "before_add_server_ban": ("server_name", "xuid"),
    "after_add_server_ban": ("server_name", "xuid"),
    "before_addon_disable": ("server_name", "pack_uuid"),
    "after_addon_disable": ("server_name", "pack_uuid"),
    "before_addon_enable": ("server_name", "pack_uuid"),
    "after_addon_enable": ("server_name", "pack_uuid"),
    "before_addon_reorder": ("server_name",),
    "after_addon_reorder": ("server_name",),
    "before_addon_uninstall": ("server_name", "pack_uuid"),
    "after_addon_uninstall": ("server_name", "pack_uuid"),
    "before_setting_update": ("key",),
    "after_setting_update": ("key",),
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
    "before_server_status_change": ("server_name", "status"),
    "after_server_status_change": ("server_name", "status"),
    "before_server_statuses_updated": ("server_name",),
    "after_server_statuses_updated": ("server_name",),
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
    "before_addon_subpack_update": ("server_name", "pack_uuid"),
    "after_addon_subpack_update": ("server_name", "pack_uuid"),
    "before_remove_server_ban": ("server_name", "xuid"),
    "after_remove_server_ban": ("server_name", "xuid"),
    "before_set_plugin_status": ("plugin_name", "new_status"),
    "after_set_plugin_status": ("plugin_name", "new_status"),
    "before_set_server_setting": ("server_name", "key"),
    "after_set_server_setting": ("server_name", "key"),
    "before_delete_server_data": ("server_name",),
    "after_delete_server_data": ("server_name",),
    "before_web_service_change": ("action",),
    "after_web_service_change": ("action",),
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
