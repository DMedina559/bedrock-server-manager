# bedrock_server_manager/api/plugins.py
"""
Provides API functions for interacting with the application's plugin system.

This module serves as an interface to the global plugin manager instance,
which is an object of
:class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager`.
It allows for retrieving plugin statuses, enabling or disabling plugins,
reloading the plugin system, and triggering custom plugin events from
external sources.

Key functionalities include:
- Getting statuses and metadata of all discovered plugins (:func:`~.get_plugin_statuses`).
- Setting the enabled/disabled state of a specific plugin (:func:`~.set_plugin_status`).
- Reloading all plugins (:func:`~.reload_plugins`).
- Triggering custom plugin events externally (:func:`~.trigger_external_plugin_event_api`).

These functions facilitate management and interaction with plugins, primarily
for use by administrative interfaces like a web UI or CLI.
"""
import logging
from typing import Dict, Any

from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method
from bedrock_server_manager.error import UserInputError

logger = logging.getLogger(__name__)


@plugin_method("get_plugin_statuses")
def get_plugin_statuses() -> Dict[str, Any]:
    """
    Retrieves the statuses and metadata of all discovered plugins.

    This function first ensures the plugin configuration is synchronized with
    the plugin files on disk by calling an internal method of the
    :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager`.
    It then returns a copy of the current plugin configuration.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "plugins": PluginConfigDict}``
        where ``PluginConfigDict`` is a dictionary mapping plugin names (str)
        to their configuration (another dict containing keys like "enabled" (bool),
        "description" (str), "version" (str)).
        On error (unexpected): ``{"status": "error", "message": "<error_message>"}``.
    """
    logger.debug("API: Attempting to get plugin statuses.")
    try:
        plugin_manager._synchronize_config_with_disk()
        # The config contains dicts like: {"enabled": bool, "description": str, "version": str}
        statuses = plugin_manager.plugin_config

        logger.info(f"API: Retrieved data for {len(statuses)} plugins.")
        return {"status": "success", "plugins": statuses.copy()}
    except Exception as e:
        logger.error(f"API: Failed to get plugin statuses: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get plugin statuses: {e}"}


def set_plugin_status(plugin_name: str, enabled: bool) -> Dict[str, Any]:
    """
    Sets the enabled/disabled status for a specific plugin.

    This function updates the ``enabled`` field for the given `plugin_name`
    in the plugin configuration, which is managed by the
    :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager`.
    The configuration is synchronized with disk before modification, and the
    changes are saved back to ``plugins.json``.

    Note:
        For the change in enabled status to take full effect (i.e., for the
        plugin to be loaded or unloaded), :func:`~.reload_plugins` typically
        needs to be called afterwards.

    Args:
        plugin_name (str): The name of the plugin to configure.
        enabled (bool): ``True`` to enable the plugin, ``False`` to disable it.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Plugin '<name>' has been <enabled/disabled>..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        UserInputError: If `plugin_name` is empty or not found in the configuration.
    """
    if not plugin_name:
        raise UserInputError("Plugin name cannot be empty.")

    logger.info(f"API: Setting status for plugin '{plugin_name}' to {enabled}.")
    try:
        # Ensure the plugin manager's config is up-to-date with disk.
        # This will also ensure plugin_name exists if it's a valid plugin.
        plugin_manager._synchronize_config_with_disk()

        if plugin_name not in plugin_manager.plugin_config:
            logger.warning(
                f"API: Attempted to configure non-existent or undiscovered plugin '{plugin_name}'."
            )
            raise UserInputError(
                f"Plugin '{plugin_name}' not found or not discoverable."
            )

        # Check if the entry for plugin_name is indeed a dictionary
        # This is a defensive check, especially if _synchronize_config_with_disk has robust migration
        if not isinstance(plugin_manager.plugin_config.get(plugin_name), dict):
            logger.error(
                f"API: Plugin '{plugin_name}' has an invalid configuration format. Expected a dictionary."
            )

            return {
                "status": "error",
                "message": f"Plugin '{plugin_name}' has an invalid configuration. Please try reloading plugins.",
            }

        # Update the 'enabled' key within the plugin's config dictionary
        plugin_manager.plugin_config[plugin_name]["enabled"] = bool(enabled)
        plugin_manager._save_config()

        action = "enabled" if enabled else "disabled"
        logger.info(f"API: Plugin '{plugin_name}' successfully {action}.")
        return {
            "status": "success",
            "message": f"Plugin '{plugin_name}' has been {action}. Reload plugins for changes to take full effect.",
        }
    except UserInputError as e:  # Catch specific UserInputError to re-raise
        raise
    except Exception as e:
        logger.error(
            f"API: Failed to set status for plugin '{plugin_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Failed to set status for plugin '{plugin_name}': {e}",
        }


def reload_plugins() -> Dict[str, Any]:
    """
    Triggers the plugin manager to unload all active plugins and
    then reload all plugins based on the current configuration.

    This function calls the `reload` method of the global
    :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager` instance.
    This process involves dispatching `on_unload` to existing plugins, clearing
    event listeners, and then re-running the full plugin discovery and loading sequence.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Plugins have been reloaded successfully."}``
        On error (unexpected): ``{"status": "error", "message": "<error_message>"}``.
    """
    logger.info("API: Attempting to reload all plugins.")
    try:
        plugin_manager.reload()  # Call the reload method on the global instance
        logger.info("API: Plugins reloaded successfully.")
        return {
            "status": "success",
            "message": "Plugins have been reloaded successfully.",
        }
    except Exception as e:
        logger.error(f"API: Failed to reload plugins: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred during plugin reload: {e}",
        }


@plugin_method("trigger_external_plugin_event_api")
def trigger_external_plugin_event_api(
    event_name: str, payload: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Allows an external source (like a web route or CLI) to trigger a custom plugin event.

    This function calls the `trigger_custom_plugin_event` method of the global
    :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager` instance.
    The `triggering_plugin_name` argument for the core method is set to
    ``"external_api_trigger"`` to identify the source of this event.

    Args:
        event_name (str): The name of the custom event to trigger. Must follow
            the 'namespace:event_name' format for custom events.
        payload (Optional[Dict[str, Any]], optional): A dictionary of data to
            pass as keyword arguments to the event listeners' callback functions.
            Defaults to ``None`` (an empty dictionary will be passed).

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Event '<event_name>' triggered."}``
        On error (e.g., invalid event name format, unexpected error during dispatch):
        ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        UserInputError: If `event_name` is empty or does not follow the
            'namespace:event_name' format required by the plugin manager.
    """
    if not event_name:
        logger.warning("API: Trigger custom event failed - event_name is required.")
        # It's better to raise an error here for the web route to catch and return 400
        raise UserInputError("Event name is required to trigger a custom plugin event.")

    logger.info(
        f"API: Attempting to trigger custom plugin event '{event_name}' externally."
    )
    try:
        actual_payload = payload if payload is not None else {}
        # "external_api_trigger" identifies the source of this event.
        plugin_manager.trigger_custom_plugin_event(
            event_name, "external_api_trigger", **actual_payload
        )
        logger.info(
            f"API: Custom plugin event '{event_name}' triggered successfully via external API."
        )
        return {"status": "success", "message": f"Event '{event_name}' triggered."}
    except Exception as e:
        logger.error(
            f"API: Unexpected error triggering custom event '{event_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred while triggering event '{event_name}': {str(e)}",
        }
