# bedrock_server_manager/web/routers/plugin.py
"""
FastAPI router for managing the application's plugin system.

This module defines endpoints for interacting with and controlling plugins.
It provides:

- API endpoints to:
    - Get the status of all discovered plugins (:func:`~.get_plugins_status_api_route`).
    - Enable or disable a specific plugin (:func:`~.set_plugin_status_api_route`).
    - Trigger a full reload of the plugin system (:func:`~.reload_plugins_api_route`).
    - Allow external triggering of custom plugin events (:func:`~.trigger_event_api_route`).

These routes interface with the underlying plugin management logic in
:mod:`~bedrock_server_manager.api.plugins` and require user authentication.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetPluginStatusesRequest,
    ReloadPluginsRequest,
    ReloadSinglePluginRequest,
    SetPluginStatusRequest,
    TriggerExternalAppEventRequest,
)

from ...api import plugins as plugins_api
from ...context import AppContext
from ...error import AppFileNotFoundError, BSMError, UserInputError
from ..deps import get_admin_user, get_app_context, get_current_user
from ..schemas import (
    ActionResponse,
    PluginPagesResponse,
    PluginStatusesResponse,
    PluginStatusSetPayload,
    TriggerEventPayload,
    TriggerEventResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Plugin Management", "Application"])


# --- API Route ---
@router.get(
    "/api/plugins/pages",
    operation_id="get_plugin_pages",
    response_model=PluginPagesResponse,
)
async def get_plugin_pages(
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> PluginPagesResponse:
    """
    Retrieves a list of custom native UI pages registered by plugins.
    """
    try:
        pages = app_context.plugin_manager.get_native_ui_routes()
        return PluginPagesResponse(status="success", pages=pages)
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"API Get Plugin Pages: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve plugin pages."
        ) from e


@router.get(
    "/api/plugins",
    operation_id="list_plugins",
    response_model=PluginStatusesResponse,
)
async def get_plugins_status(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> PluginStatusesResponse:
    """
    Retrieves the statuses and metadata of all discovered plugins.
    """
    identity = current_user.username
    logger.info(f"API: Get plugin statuses request by '{identity}'.")
    try:
        result = await plugins_api.get_plugin_statuses(
            request=GetPluginStatusesRequest(), app_context=app_context
        )
        return PluginStatusesResponse(status="success", plugins=result.plugins)
    except HTTPException:
        raise
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"API Get Plugin Statuses: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while getting plugin statuses.",
        )


@router.post(
    "/api/plugins/trigger_event",
    operation_id="trigger_plugin_event",
    response_model=TriggerEventResponse,
)
async def post_trigger_event(
    payload: TriggerEventPayload,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TriggerEventResponse:
    """
    Allows an external source to trigger a custom plugin event within the system.
    """
    identity = current_user.username
    logger.info(
        f"API: Custom plugin event '{payload.event_name}' trigger request by '{identity}'."
    )

    try:
        result = await plugins_api.trigger_external_app_event(
            request=TriggerExternalAppEventRequest(
                event_name=payload.event_name, payload=payload.payload
            ),
            app_context=app_context,
        )
        return TriggerEventResponse(
            status=result.status,
            message=result.message,
        )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except AppFileNotFoundError:
        raise
    except BSMError as e:
        logger.error(
            f"API Trigger Event '{payload.event_name}': BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(
            f"API Trigger Event '{payload.event_name}': Unexpected error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while triggering the event.",
        )


@router.post(
    "/api/plugins/{plugin_name}",
    operation_id="set_plugin_status",
    response_model=ActionResponse,
)
async def post_set_plugin_status(
    plugin_name: str,
    payload: PluginStatusSetPayload,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> ActionResponse:
    """
    Sets the enabled or disabled status for a specific plugin.
    """
    identity = current_user.username
    action = "enable" if payload.enabled else "disable"
    logger.info(
        f"API: Request to {action} plugin '{plugin_name}' by user '{identity}'."
    )

    try:
        result = await plugins_api.set_plugin_status(
            request=SetPluginStatusRequest(
                target_plugin_name=plugin_name, enabled=payload.enabled
            ),
            app_context=app_context,
        )
        return ActionResponse(status=result.status, message=str(result.message))

    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except AppFileNotFoundError:
        raise
    except BSMError as e:
        logger.error(f"API Set Plugin '{plugin_name}': BSMError: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(
            f"API Set Plugin '{plugin_name}': Unexpected error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while trying to {action} the plugin.",
        )


@router.post(
    "/api/plugins/{plugin_name}/reload",
    operation_id="reload_plugin",
    response_model=ActionResponse,
)
async def post_reload_single_plugin(
    plugin_name: str,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> ActionResponse:
    """
    Reloads a single plugin by name.
    """
    identity = current_user.username
    logger.info(f"API: Request to reload plugin '{plugin_name}' by user '{identity}'.")

    try:
        result = await plugins_api.reload_single_plugin(
            request=ReloadSinglePluginRequest(target_plugin_name=plugin_name),
            app_context=app_context,
        )
        return ActionResponse(status=result.status, message=str(result.message))

    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except AppFileNotFoundError:
        raise
    except BSMError as e:
        logger.error(f"API Reload Plugin '{plugin_name}': BSMError: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(
            f"API Reload Plugin '{plugin_name}': Unexpected error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while reloading plugin '{plugin_name}'.",
        )


@router.put(
    "/api/plugins/reload", operation_id="reload_plugins", response_model=ActionResponse
)
async def put_reload_plugins(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> ActionResponse:
    """
    Triggers a full reload of the plugin system.
    """
    identity = current_user.username
    logger.info(f"API: Reload plugins request by '{identity}'.")

    try:
        result = await plugins_api.reload_plugins(
            request=ReloadPluginsRequest(), app_context=app_context
        )
        return ActionResponse(status=result.status, message=str(result.message))
    except HTTPException:
        raise
    except AppFileNotFoundError:
        raise
    except BSMError as e:
        logger.error(f"API Reload Plugins: BSMError: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"API Reload Plugins: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while reloading plugins.",
        )
