# bedrock_server_manager/api/settings.py
"""Provide an API for interacting with global application settings."""

import logging

from pydantic import ValidationError

from ..context import AppContext
from ..error import BSMError, UserInputError
from ..events import trigger_event
from ..logging import log_operation_error
from ..models.settings import (
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
from ..plugins.api_bridge import api_method
from ..plugins.scopes import (
    BLACKLISTED_PATH_SETTINGS,
    GRANTABLE_PATH_SCOPES,
    plugin_has_permission,
    require_plugin_permission,
)

logger = logging.getLogger(__name__)


@api_method("get_global_setting")
async def get_global_setting(
    request: GetGlobalSettingRequest,
    *,
    app_context: AppContext,
    plugin_name: str | None = None,
) -> GetGlobalSettingResponse:
    """Reads a single value from the global application settings."""
    key = request.key
    if plugin_name is not None and (key == "paths" or key.startswith("paths.")):
        if key in BLACKLISTED_PATH_SETTINGS:
            raise PermissionError(f"Access to '{key}' is restricted for all plugins.")
        scope = key.split(".", 1)[1] if "." in key else None
        if scope not in GRANTABLE_PATH_SCOPES:
            raise PermissionError(
                f"Access to host filesystem path '{key}' is restricted for plugins."
            )
        require_plugin_permission(app_context, plugin_name, f"path:{scope}")
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
    request: GetAllGlobalSettingsRequest,
    *,
    app_context: AppContext,
    plugin_name: str | None = None,
) -> GetAllGlobalSettingsResponse:
    """Reads the entire global application settings configuration."""
    logger.debug("Reading all global settings.")
    try:
        settings = app_context.settings
        all_settings = dict(settings.state.settings.to_dict())
        if plugin_name is not None:
            paths = all_settings.get("paths")
            if isinstance(paths, dict):
                plugin = app_context.plugin_manager.get_plugin(plugin_name)
                filtered_paths = {}
                for scope in GRANTABLE_PATH_SCOPES:
                    if (
                        plugin_has_permission(plugin, f"path:{scope}")
                        and scope in paths
                    ):
                        filtered_paths[scope] = paths[scope]
                if filtered_paths:
                    all_settings["paths"] = filtered_paths
                else:
                    all_settings.pop("paths", None)
            else:
                all_settings.pop("paths", None)
        logger.debug("Successfully retrieved all global settings.")
        return GetAllGlobalSettingsResponse.model_validate(
            {"status": "success", "settings": all_settings}
        )
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error reading all global settings: %s", e, error=e
        )
        raise


@api_method("set_global_setting", expose_to_plugins=False)
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


@api_method("reload_global_settings", expose_to_plugins=False)
async def reload_global_settings(
    request: ReloadGlobalSettingsRequest, *, app_context: AppContext
) -> ReloadGlobalSettingsResponse:
    """Forces a reload of settings and logging config from the file."""
    logger.debug("Received request to reload global settings and logging.")
    try:
        await app_context.reload()
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
