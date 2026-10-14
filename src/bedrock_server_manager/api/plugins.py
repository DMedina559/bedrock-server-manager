# bedrock_server_manager/api/plugins.py
"""Provide API functions for interacting with the application's plugin system."""

import logging

from pydantic import ValidationError

from ..context import AppContext
from ..error import BSMError, UserInputError
from ..events import trigger_event
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..plugins.api_contract import validate_contract
from .models.plugins import (
    EventDispatchSummary,
    GetPluginSettingRequest,
    GetPluginSettingResponse,
    GetPluginSettingsRequest,
    GetPluginSettingsResponse,
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
    UpdatePluginSettingsRequest,
)

logger = logging.getLogger(__name__)


@api_method("get_plugin_statuses")
async def get_plugin_statuses(
    request: GetPluginStatusesRequest, *, app_context: AppContext
) -> GetPluginStatusesResponse:
    """Return the statuses and metadata of all discovered plugins."""
    logger.debug("Attempting to get plugin statuses.")
    try:
        pm = app_context.plugin_manager
        await pm._synchronize_config_with_disk()
        statuses = {
            name: {
                **config,
                "status": pm.get_plugin_status(name),
                "has_settings": bool(
                    app_context.plugin_service.get_settings(name)
                    or (
                        name in app_context.plugin_service.settings_models
                        and app_context.plugin_service.settings_models[
                            name
                        ].model_fields
                    )
                ),
            }
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
    """Set the enabled/disabled status for a specific plugin."""
    plugin_name = request.target_plugin_name
    enabled = request.enabled
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
        return SetPluginStatusResponse(
            status="success", message=f"Plugin '{plugin_name}' has been {action}."
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
    """Reloads a single plugin by name."""
    plugin_name = request.target_plugin_name
    logger.debug("Attempting to reload plugin '%s'.", plugin_name)
    try:
        pm = app_context.plugin_manager
        success = await pm.reload_plugin(plugin_name)
        if success:
            logger.info("Plugin '%s' reloaded successfully.", plugin_name)
            return ReloadSinglePluginResponse(
                status="success",
                message=f"Plugin '{plugin_name}' reloaded successfully.",
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
    """Triggers the plugin manager to unload all active plugins and"""
    logger.debug("Attempting to reload all plugins.")
    try:
        pm = app_context.plugin_manager
        await pm.reload()
        logger.info("Plugins reloaded successfully.")
        return ReloadPluginsResponse(
            status="success", message="Plugins have been reloaded successfully."
        )
    except Exception as e:
        log_operation_error(logger, "Failed to reload plugins: %s", e, error=e)
        raise


@validate_contract
async def trigger_external_app_event(
    request: TriggerExternalAppEventRequest, *, app_context: AppContext
) -> TriggerExternalAppEventResponse:
    """Allows an external source (like a web route or CLI) to trigger a custom plugin
    event.
    """
    event_name = request.event_name
    payload = request.payload
    logger.debug(
        "Attempting to trigger custom plugin event '%s' externally.", event_name
    )
    try:
        definition = app_context.events.registry.definition(event_name)
        if definition.phase != "custom":
            raise UserInputError("Only custom events may be triggered externally")
        actual_payload = payload if payload is not None else {}
        record = await app_context.events.emit(
            event_name, actual_payload, source="external_api"
        )
        logger.debug(
            "Custom plugin event '%s' triggered successfully via external API.",
            event_name,
        )
        return TriggerExternalAppEventResponse(
            status=(
                "partial"
                if record.status == "partial"
                else "skipped" if record.status == "suppressed" else "success"
            ),
            message=f"Event '{event_name}' dispatched.",
            details=EventDispatchSummary(
                event_id=record.event_id,
                listeners_called=record.listeners_called,
                failures=record.failures,
            ),
        )
    except ValidationError as error:
        raise UserInputError(
            "Custom event payload does not match its declared contract"
        ) from error
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
@trigger_event(after="after_plugin_settings_update")
async def set_plugin_setting(
    request: SetPluginSettingRequest, *, app_context: AppContext, plugin_name: str
) -> SetPluginSettingResponse:
    """Persist settings scoped to the bridge-injected plugin identity."""
    await app_context.plugin_service.set_setting(
        plugin_name, request.key, request.value
    )
    return SetPluginSettingResponse(message="Plugin setting saved.")


@validate_contract
async def get_plugin_settings(
    request: GetPluginSettingsRequest, *, app_context: AppContext
) -> GetPluginSettingsResponse:
    name = request.target_plugin_name
    if app_context.plugin_service.get_plugin_state(name) is None:
        raise UserInputError("Unknown plugin.")
    service = app_context.plugin_service
    return GetPluginSettingsResponse(
        settings=service.get_settings(name),
        settings_schema=service.get_settings_schema(name),
    )


@validate_contract
@trigger_event(after="after_plugin_settings_update")
async def update_plugin_settings(
    request: UpdatePluginSettingsRequest, *, app_context: AppContext
) -> SetPluginSettingResponse:
    if app_context.plugin_service.get_plugin_state(request.target_plugin_name) is None:
        raise UserInputError("Unknown plugin.")
    await app_context.plugin_service.replace_settings(
        request.target_plugin_name, request.settings
    )
    return SetPluginSettingResponse(message="Plugin settings saved.")
