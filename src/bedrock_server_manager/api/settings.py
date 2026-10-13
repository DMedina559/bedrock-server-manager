# bedrock_server_manager/api/settings.py
"""Provide an API for interacting with global application settings."""

import logging

from pydantic import ValidationError

from ..context import AppContext
from ..error import BSMError, UserInputError
from ..events import trigger_event
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..plugins.api_contract import validate_contract
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
    """Reads a single value from the global application settings."""
    key = request.key
    logger.debug("Reading global setting '%s'.", key)
    try:
        settings = app_context.settings
        retrieved_value = settings.get(key)
        logger.debug("Successfully read global setting '%s'.", key)
        return GetGlobalSettingResponse.model_validate(
            {"status": "success", "value": retrieved_value}
        )
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error reading global setting '%s': %s", key, e, error=e
        )
        raise


@api_method("get_all_global_settings")
async def get_all_global_settings(
    request: GetAllGlobalSettingsRequest, *, app_context: AppContext
) -> GetAllGlobalSettingsResponse:
    """Reads the entire global application settings configuration."""
    logger.debug("Reading all global settings.")
    try:
        settings = app_context.settings
        all_settings = settings.state.settings.to_dict()
        logger.debug("Successfully retrieved all global settings.")
        return GetAllGlobalSettingsResponse.model_validate(
            {"status": "success", "settings": all_settings}
        )
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error reading all global settings: %s", e, error=e
        )
        raise


@validate_contract
@trigger_event(
    before="before_setting_update", after="after_setting_update", identity_keys=("key",)
)
async def set_global_setting(
    request: SetGlobalSettingRequest, *, app_context: AppContext
) -> SetGlobalSettingResponse:
    """Writes a value to the global application settings."""
    key = request.key
    value = request.value
    logger.debug("Updating global setting '%s'.", key)
    try:
        settings = app_context.settings
        await settings.set(key, value)
        logger.info("Successfully wrote to global setting '%s'.", key)
        return SetGlobalSettingResponse(
            message=f"Global setting '{key}' updated successfully."
        )
    except ValidationError as error:
        raise UserInputError("Invalid setting value.") from error
    except BSMError as e:
        log_operation_error(
            logger, "Configuration error setting global key '%s': %s", key, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error setting global key '%s': %s", key, e, error=e
        )
        raise


@api_method("set_custom_global_setting")
async def set_custom_global_setting(
    request: SetCustomGlobalSettingRequest, *, app_context: AppContext
) -> SetCustomGlobalSettingResponse:
    """Writes a custom value to the global application settings."""
    key = request.key
    value = request.value
    key = "custom." + key.strip()
    logger.debug("Updating global setting '%s'.", key)
    try:
        settings = app_context.settings
        await settings.set(key, value)
        logger.info("Successfully wrote to global setting '%s'.", key)
        return SetCustomGlobalSettingResponse(
            message=f"Global setting '{key}' updated successfully."
        )
    except ValidationError as error:
        raise UserInputError("Invalid setting value.") from error
    except BSMError as e:
        log_operation_error(
            logger, "Configuration error setting global key '%s': %s", key, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error setting global key '%s': %s", key, e, error=e
        )
        raise


@validate_contract
async def reload_global_settings(
    request: ReloadGlobalSettingsRequest, *, app_context: AppContext
) -> ReloadGlobalSettingsResponse:
    """Forces a reload of settings and logging config from the file."""
    logger.debug("Received request to reload global settings and logging.")
    try:
        await app_context.reload()
        settings = app_context.settings
        await settings.reload()
        logger.info("Global settings successfully reloaded.")
        return ReloadGlobalSettingsResponse(
            message="Global settings have been reloaded."
        )
    except BSMError as e:
        log_operation_error(logger, "Error reloading settings: %s", e, error=e)
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error reloading settings: %s", e, error=e
        )
        raise
