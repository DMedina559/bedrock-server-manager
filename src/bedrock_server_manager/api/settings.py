# bedrock_server_manager/api/settings.py
"""Provides an API for interacting with global application settings.

This module offers functions to read, write, and reload application-wide
configuration values. These settings are managed by the
:class:`~bedrock_server_manager.config.settings.Settings` class and are
typically stored in the main ``bedrock_server_manager.json`` configuration file.

The functions provided here allow other parts of the application, including
plugins (via methods exposed by
:func:`~bedrock_server_manager.plugins.api_bridge.api_method`), to
programmatically access and modify these global settings.
"""

import logging

from ..context import AppContext
from ..error import BSMError, MissingArgumentError
from ..plugins.api_bridge import api_method
from ..plugins.api_contract import validate_contract
from ..plugins.event_trigger import trigger_event
from .models.settings import (
    GetAllGlobalSettingsRequest,
    GetAllGlobalSettingsResponse,
    GetGlobalSettingRequest,
    GetGlobalSettingResponse,
    ReloadGlobalSettingsRequest,
    ReloadGlobalSettingsResponse,
    SetCustomGlobalSettingRequest,
    SetCustomGlobalSettingResponse,
    SetGlobalSettingRequest,
    SetGlobalSettingResponse,
)

logger = logging.getLogger(__name__)


@api_method("get_global_setting")
async def get_global_setting(
    request: GetGlobalSettingRequest, *, app_context: AppContext
) -> GetGlobalSettingResponse:
    """Reads a single value from the global application settings.

    Accepts GetGlobalSettingRequest and returns GetGlobalSettingResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    key = request.key
    if not key:
        raise MissingArgumentError("A 'key' must be provided to get a setting.")
    logger.debug(f"API: Reading global setting '{key}'.")
    try:
        settings = app_context.settings
        retrieved_value = settings.get(key)
        logger.debug(f"API: Successfully read global setting '{key}'.")
        return GetGlobalSettingResponse.model_validate(
            {"status": "success", "value": retrieved_value}
        )
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading global setting '{key}': {e}", exc_info=True
        )
        raise


@api_method("get_all_global_settings")
async def get_all_global_settings(
    request: GetAllGlobalSettingsRequest, *, app_context: AppContext
) -> GetAllGlobalSettingsResponse:
    """Reads the entire global application settings configuration.

    Accepts GetAllGlobalSettingsRequest and returns GetAllGlobalSettingsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.debug("API: Reading all global settings.")
    try:
        settings = app_context.settings
        all_settings = settings._settings.copy()
        logger.debug("API: Successfully retrieved all global settings.")
        return GetAllGlobalSettingsResponse.model_validate(
            {"status": "success", "settings": all_settings}
        )
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading all global settings: {e}", exc_info=True
        )
        raise


@validate_contract
@trigger_event(
    before="before_setting_update", after="after_setting_update", identity_keys=("key",)
)
async def set_global_setting(
    request: SetGlobalSettingRequest, *, app_context: AppContext
) -> SetGlobalSettingResponse:
    """Writes a value to the global application settings.

    Accepts SetGlobalSettingRequest and returns SetGlobalSettingResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    key = request.key
    value = request.value
    if not key:
        raise MissingArgumentError("A 'key' must be provided to set a setting.")
    logger.debug(f"API: Writing to global setting. Key='{key}', Value='{value}'")
    try:
        settings = app_context.settings
        await settings.set(key, value)
        logger.info(f"API: Successfully wrote to global setting '{key}'.")
        return SetGlobalSettingResponse(
            message=f"Global setting '{key}' updated successfully."
        )
    except BSMError as e:
        logger.error(
            f"API: Configuration error setting global key '{key}': {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting global key '{key}': {e}", exc_info=True
        )
        raise


@api_method("set_custom_global_setting")
async def set_custom_global_setting(
    request: SetCustomGlobalSettingRequest, *, app_context: AppContext
) -> SetCustomGlobalSettingResponse:
    """Writes a custom value to the global application settings.

    Accepts SetCustomGlobalSettingRequest and returns SetCustomGlobalSettingResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    key = request.key
    value = request.value
    if not key:
        raise MissingArgumentError("A 'key' must be provided to set a setting.")
    key = "custom." + key.strip()
    logger.debug(f"API: Writing to global setting. Key='{key}', Value='{value}'")
    try:
        settings = app_context.settings
        await settings.set(key, value)
        logger.info(f"API: Successfully wrote to global setting '{key}'.")
        return SetCustomGlobalSettingResponse(
            message=f"Global setting '{key}' updated successfully."
        )
    except BSMError as e:
        logger.error(
            f"API: Configuration error setting global key '{key}': {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting global key '{key}': {e}", exc_info=True
        )
        raise


@validate_contract
async def reload_global_settings(
    request: ReloadGlobalSettingsRequest, *, app_context: AppContext
) -> ReloadGlobalSettingsResponse:
    """Forces a reload of settings and logging config from the file.

    Accepts ReloadGlobalSettingsRequest and returns ReloadGlobalSettingsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.info("API: Received request to reload global settings and logging.")
    try:
        await app_context.reload()
        settings = app_context.settings
        await settings.reload()
        logger.info("API: Global settings successfully reloaded.")
        return ReloadGlobalSettingsResponse(
            message="Global settings have been reloaded."
        )
    except BSMError as e:
        logger.error(f"API: Error reloading settings: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"API: Unexpected error reloading settings: {e}", exc_info=True)
        raise
