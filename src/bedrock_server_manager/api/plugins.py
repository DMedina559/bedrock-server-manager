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
- Triggering custom plugin events externally (:func:`~.trigger_external_app_event`).

These functions facilitate management and interaction with plugins, primarily
for use by administrative interfaces like a web UI or CLI.
"""

import logging

from ..context import AppContext
from ..error import BSMError, UserInputError
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..plugins.api_contract import validate_contract
from ..plugins.event_trigger import trigger_event
from .models.plugins import (
    GetPluginSettingRequest,
    GetPluginSettingResponse,
    GetPluginStatusesRequest,
    GetPluginStatusesResponse,
    ReloadPluginsRequest,
    ReloadPluginsResponse,
    ReloadSinglePluginRequest,
    ReloadSinglePluginResponse,
    SetPluginSettingRequest,
    SetPluginSettingResponse,
    SetPluginStatusRequest,
    SetPluginStatusResponse,
    TriggerExternalAppEventRequest,
    TriggerExternalAppEventResponse,
)

logger = logging.getLogger(__name__)


@api_method("get_plugin_statuses")
async def get_plugin_statuses(
    request: GetPluginStatusesRequest, *, app_context: AppContext
) -> GetPluginStatusesResponse:
    """Retrieves the statuses and metadata of all discovered plugins.

    Accepts GetPluginStatusesRequest and returns GetPluginStatusesResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.debug("Attempting to get plugin statuses.")
    try:
        pm = app_context.plugin_manager
        await pm._synchronize_config_with_disk()
        statuses = {
            name: {**config, "status": pm.get_plugin_status(name)}
            for name, config in pm.plugin_config.items()
        }
        logger.debug("Retrieved data for %s plugins.", len(statuses))
        return GetPluginStatusesResponse.model_validate(
            {"status": "success", "plugins": statuses.copy()}
        )
    except Exception as e:
        log_operation_error(logger, "Failed to get plugin statuses: %s", e, error=e)
        raise


@validate_contract
@trigger_event(
    before="before_set_plugin_status",
    after="after_set_plugin_status",
    identity_keys=("plugin_name", "enabled"),
)
async def set_plugin_status(
    request: SetPluginStatusRequest, *, app_context: AppContext
) -> SetPluginStatusResponse:
    """Sets the enabled/disabled status for a specific plugin.

    Accepts SetPluginStatusRequest and returns SetPluginStatusResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    plugin_name = request.target_plugin_name
    enabled = request.enabled
    if not plugin_name:
        raise UserInputError("Plugin name cannot be empty.")
    logger.debug("Setting status for plugin '%s' to %s.", plugin_name, enabled)
    try:
        pm = app_context.plugin_manager
        await pm._synchronize_config_with_disk()
        if plugin_name not in pm.plugin_config:
            raise UserInputError(
                f"Plugin '{plugin_name}' not found or not discoverable."
            )
        if not isinstance(pm.plugin_config.get(plugin_name), dict):
            raise BSMError(
                f"Plugin '{plugin_name}' has an invalid configuration. Please try reloading plugins."
            )
        if enabled:
            changed = await pm.enable_plugin(plugin_name, load_immediately=True)
        else:
            changed = await pm.disable_plugin(plugin_name, unload_immediately=True)
        if not changed:
            raise BSMError(
                f"Could not change runtime status for plugin '{plugin_name}'."
            )
        action = "enabled" if enabled else "disabled"
        logger.info("Plugin '%s' successfully %s.", plugin_name, action)
        return SetPluginStatusResponse.model_validate(
            {
                "status": "success",
                "message": f"Plugin '{plugin_name}' has been {action}.",
            }
        )
    except UserInputError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "Failed to set status for plugin '%s': %s", plugin_name, e, error=e
        )
        raise


@api_method("reload_plugin", expose_to_plugins=False)
async def reload_single_plugin(
    request: ReloadSinglePluginRequest, *, app_context: AppContext
) -> ReloadSinglePluginResponse:
    """Reloads a single plugin by name.

    Accepts ReloadSinglePluginRequest and returns ReloadSinglePluginResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    plugin_name = request.target_plugin_name
    if not plugin_name:
        raise UserInputError("Plugin name cannot be empty.")
    logger.debug("Attempting to reload plugin '%s'.", plugin_name)
    try:
        pm = app_context.plugin_manager
        success = await pm.reload_plugin(plugin_name)
        if success:
            logger.info("Plugin '%s' reloaded successfully.", plugin_name)
            return ReloadSinglePluginResponse.model_validate(
                {
                    "status": "success",
                    "message": f"Plugin '{plugin_name}' reloaded successfully.",
                }
            )
        else:
            raise BSMError(f"Failed to reload plugin '{plugin_name}'.")
    except Exception as e:
        log_operation_error(
            logger, "Failed to reload plugin '%s': %s", plugin_name, e, error=e
        )
        raise


@validate_contract
async def reload_plugins(
    request: ReloadPluginsRequest, *, app_context: AppContext
) -> ReloadPluginsResponse:
    """Triggers the plugin manager to unload all active plugins and

    Accepts ReloadPluginsRequest and returns ReloadPluginsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.debug("Attempting to reload all plugins.")
    try:
        pm = app_context.plugin_manager
        await pm.reload()
        logger.info("Plugins reloaded successfully.")
        return ReloadPluginsResponse.model_validate(
            {"status": "success", "message": "Plugins have been reloaded successfully."}
        )
    except Exception as e:
        log_operation_error(logger, "Failed to reload plugins: %s", e, error=e)
        raise


@validate_contract
async def trigger_external_app_event(
    request: TriggerExternalAppEventRequest, *, app_context: AppContext
) -> TriggerExternalAppEventResponse:
    """Allows an external source (like a web route or CLI) to trigger a custom plugin event.

    Accepts TriggerExternalAppEventRequest and returns TriggerExternalAppEventResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    event_name = request.event_name
    payload = request.payload
    if not event_name:
        raise UserInputError("Event name is required to trigger a custom plugin event.")
    logger.debug(
        "Attempting to trigger custom plugin event '%s' externally.", event_name
    )
    try:
        pm = app_context.plugin_manager
        actual_payload = payload if payload is not None else {}
        await pm.trigger_event(
            event_name, **actual_payload, _triggering_plugin="external_api_trigger"
        )
        logger.debug(
            "Custom plugin event '%s' triggered successfully via external API.",
            event_name,
        )
        return TriggerExternalAppEventResponse.model_validate(
            {"status": "success", "message": f"Event '{event_name}' triggered."}
        )
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error triggering custom event '%s': %s",
            event_name,
            e,
            error=e,
        )
        raise


@api_method("get_plugin_setting")
async def get_plugin_setting(
    request: GetPluginSettingRequest, *, app_context: AppContext, plugin_name: str
) -> GetPluginSettingResponse:
    """Read settings scoped to the bridge-injected plugin identity."""
    return GetPluginSettingResponse(
        value=app_context.plugin_service.get_setting(plugin_name, request.key)
    )


@api_method("set_plugin_setting")
async def set_plugin_setting(
    request: SetPluginSettingRequest, *, app_context: AppContext, plugin_name: str
) -> SetPluginSettingResponse:
    """Persist settings scoped to the bridge-injected plugin identity."""
    await app_context.plugin_service.set_setting(
        plugin_name, request.key, request.value
    )
    return SetPluginSettingResponse(message="Plugin setting saved.")
