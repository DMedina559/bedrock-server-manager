# bedrock_server_manager/api/settings.py
"""Provides an API for interacting with global application settings.

This module offers functions to read, write, and reload application-wide
configuration values. These settings are managed by the
:class:`~bedrock_server_manager.config.settings.Settings` class and are
typically stored in the main ``bedrock_server_manager.json`` configuration file.

The functions provided here allow other parts of the application, including
plugins (via methods exposed by
:func:`~bedrock_server_manager.plugins.api_bridge.plugin_method`), to
programmatically access and modify these global settings.
"""
import logging
from typing import Any, Dict

# Plugin system imports to bridge API functionality.
from bedrock_server_manager.plugins.api_bridge import plugin_method
from bedrock_server_manager.logging import setup_logging

# Local application imports.
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    BSMError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)


@plugin_method("get_global_setting")
def get_global_setting(key: str) -> Dict[str, Any]:
    """Reads a single value from the global application settings.

    This function uses :meth:`~bedrock_server_manager.config.settings.Settings.get`
    to retrieve the value associated with the given `key`.

    Args:
        key (str): The dot-notation key for the setting (e.g., "paths.backups",
            "web.port").

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "value": <retrieved_value>}``.
        The ``<retrieved_value>`` will be ``None`` if the key does not exist in the settings.
        On error (unexpected): ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `key` is empty.
    """
    if not key:
        raise MissingArgumentError("A 'key' must be provided to get a setting.")

    logger.debug(f"API: Reading global setting '{key}'.")
    try:
        retrieved_value = settings.get(key)
        logger.debug(f"API: Successfully read global setting '{key}'.")
        return {
            "status": "success",
            "value": retrieved_value,
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading global setting '{key}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred while reading setting '{key}': {e}",
        }


@plugin_method("get_all_global_settings")
def get_all_global_settings() -> Dict[str, Any]:
    """Reads the entire global application settings configuration.

    Returns a copy of all currently loaded settings from the
    :class:`~bedrock_server_manager.config.settings.Settings` instance.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "data": <all_settings_dict>}``.
        On error (unexpected): ``{"status": "error", "message": "<error_message>"}``.
    """
    logger.debug("API: Reading all global settings.")
    try:
        # Accessing _settings is an internal detail, but this API provides
        # a controlled public interface to it. A copy is returned.
        all_settings = settings._settings.copy()
        logger.debug("API: Successfully retrieved all global settings.")
        return {
            "status": "success",
            "data": all_settings,
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading all global settings: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {e}",
        }


def set_global_setting(key: str, value: Any) -> Dict[str, Any]:
    """Writes a value to the global application settings.

    This function uses :meth:`~bedrock_server_manager.config.settings.Settings.set`
    to update the value associated with the given `key` and persists the
    changes to the main application configuration file (e.g., ``bedrock_server_manager.json``).

    Args:
        key (str): The dot-notation key for the setting to update (e.g., "web.port",
            "paths.backups").
        value (Any): The new value to set. This value must be JSON-serializable.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Global setting '<key>' updated successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        MissingArgumentError: If `key` is empty.
        BSMError: Can be raised by :meth:`~bedrock_server_manager.config.settings.Settings.set`
            for issues like write errors (e.g., :class:`~.error.ConfigWriteError`)
            or if the value is not JSON serializable.
    """
    if not key:
        raise MissingArgumentError("A 'key' must be provided to set a setting.")

    logger.debug(f"API: Writing to global setting. Key='{key}', Value='{value}'")
    try:
        settings.set(key, value)
        logger.info(f"API: Successfully wrote to global setting '{key}'.")
        return {
            "status": "success",
            "message": f"Global setting '{key}' updated successfully.",
        }
    except BSMError as e:
        logger.error(
            f"API: Configuration error setting global key '{key}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Failed to set setting '{key}': {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting global key '{key}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred while setting '{key}': {e}",
        }


@plugin_method("set_custom_global_setting")
def set_custom_global_setting(key: str, value: Any) -> Dict[str, Any]:
    """Writes a custom value to the global application settings.

    This function uses :meth:`~bedrock_server_manager.config.settings.Settings.set`
    to update the value associated with the given `key` and persists the
    changes to the main application configuration file (e.g., ``bedrock_server_manager.json``).

    Args:
        key (str): The key for the setting to update (e.g., "custom_dir",
            "somekey"). This will be prefixed with "custom.".
        value (Any): The new value to set. This value must be JSON-serializable.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Global setting '<key>' updated successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        MissingArgumentError: If `key` is empty.
        BSMError: Can be raised by :meth:`~bedrock_server_manager.config.settings.Settings.set`
            for issues like write errors (e.g., :class:`~.error.ConfigWriteError`)
            or if the value is not JSON serializable.
    """
    if not key:
        raise MissingArgumentError("A 'key' must be provided to set a setting.")

    key = "custom." + key.strip()  # Prefix to indicate custom settings

    logger.debug(f"API: Writing to global setting. Key='{key}', Value='{value}'")
    try:
        settings.set(key, value)
        logger.info(f"API: Successfully wrote to global setting '{key}'.")
        return {
            "status": "success",
            "message": f"Global setting '{key}' updated successfully.",
        }
    except BSMError as e:
        logger.error(
            f"API: Configuration error setting global key '{key}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Failed to set setting '{key}': {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting global key '{key}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred while setting '{key}': {e}",
        }


def reload_global_settings() -> Dict[str, str]:
    """
    Forces a reload of settings and logging config from the file.

    This is useful if ``bedrock_server_manager.json`` has been edited
    manually and the application needs to pick up the changes without restarting.
    It calls :meth:`~bedrock_server_manager.config.settings.Settings.reload`
    to re-read the configuration file, and then calls
    :func:`~bedrock_server_manager.logging.setup_logging` to re-apply
    the logging configuration based on the (potentially) new settings.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Global settings and logging configuration have been reloaded."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        BSMError: Can be raised by :meth:`~bedrock_server_manager.config.settings.Settings.reload`
            (e.g., :class:`~.error.ConfigLoadError`) or by
            :func:`~bedrock_server_manager.logging.setup_logging` if critical
            logging settings are missing or invalid after reload.
    """
    logger.info("API: Received request to reload global settings and logging.")
    try:
        # Step 1: Reload the settings from the file
        settings.reload()
        logger.info("API: Global settings successfully reloaded.")

        # Step 2: Re-apply logging configuration with the new settings
        logger.info("API: Re-applying logging configuration...")
        setup_logging(
            log_dir=settings.get("paths.logs"),
            log_keep=settings.get("retention.logs"),
            file_log_level=settings.get("logging.file_level"),
            cli_log_level=settings.get("logging.cli_level"),
            force_reconfigure=True,  # Crucial flag to force removal of old handlers
        )
        logger.info("API: Logging configuration successfully re-applied.")

        return {
            "status": "success",
            "message": "Global settings and logging configuration have been reloaded.",
        }
    except BSMError as e:
        logger.error(f"API: Error reloading settings/logging: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"A configuration error occurred during reload: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error reloading settings/logging: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred during reload: {e}",
        }
