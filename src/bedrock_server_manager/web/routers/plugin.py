# bedrock_server_manager/web/routers/plugin.py
"""
FastAPI router for managing the application's plugin system.

This module defines endpoints for interacting with and controlling plugins.
It provides:

- An HTML page for managing plugins (:func:`~.manage_plugins_page_route`).
- API endpoints to:
    - Get the status of all discovered plugins (:func:`~.get_plugins_status_api_route`).
    - Enable or disable a specific plugin (:func:`~.set_plugin_status_api_route`).
    - Trigger a full reload of the plugin system (:func:`~.reload_plugins_api_route`).
    - Allow external triggering of custom plugin events (:func:`~.trigger_event_api_route`).

These routes interface with the underlying plugin management logic in
:mod:`~bedrock_server_manager.api.plugins` and require user authentication.
"""
import logging
from typing import Dict, Any, List, Optional

from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from bedrock_server_manager.web.templating import templates
from bedrock_server_manager.web.auth_utils import get_current_user
from bedrock_server_manager.api import plugins as plugins_api
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["Plugin Management"])


# --- Corrected Pydantic Models ---
class PluginStatusSetPayload(BaseModel):
    """Request model for setting a plugin's enabled status."""

    enabled: bool = Field(
        ..., description="Set to true to enable the plugin, false to disable."
    )


class TriggerEventPayload(BaseModel):
    """Request model for triggering a custom plugin event."""

    event_name: str = Field(
        ...,
        min_length=1,
        description="The namespaced name of the event to trigger (e.g., 'myplugin:myevent').",
    )
    payload: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional dictionary payload for the event."
    )


class GeneralPluginApiResponse(BaseModel):
    """Generic API response model for plugin operations."""

    status: str = Field(
        ..., description="Status of the operation (e.g., 'success', 'error')."
    )
    message: Optional[str] = Field(
        default=None, description="Optional descriptive message."
    )
    data: Optional[Any] = Field(
        default=None,
        description="Optional data payload, structure depends on the endpoint (e.g., plugin statuses).",
    )


# --- HTML Route ---
@router.get("/", response_class=HTMLResponse, name="manage_plugins_page")
async def manage_plugins_page_route(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Serves the HTML page for managing installed plugins.

    This page typically allows users to view discovered plugins,
    their statuses (enabled/disabled), versions, and descriptions,
    and provides controls to enable/disable or reload plugins.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"User '{identity}' accessed plugin management page.")
    return templates.TemplateResponse(
        "manage_plugins.html", {"request": request, "current_user": current_user}
    )


# --- API Route ---
@router.get("/api", response_model=GeneralPluginApiResponse, tags=["Plugin API"])
async def get_plugins_status_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieves the statuses and metadata of all discovered plugins.

    Calls :func:`~bedrock_server_manager.api.plugins.get_plugin_statuses`
    to get the current configuration and state of all plugins.
    The response includes whether each plugin is enabled, its description,
    and version.

    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Get plugin statuses request by '{identity}'.")
    try:
        result = plugins_api.get_plugin_statuses()
        if result.get("status") == "success":
            return GeneralPluginApiResponse(
                status="success", data=result.get("plugins")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to get plugin statuses."),
            )
    except Exception as e:
        logger.error(f"API Get Plugin Statuses: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while getting plugin statuses.",
        )


# --- API Route ---
@router.post(
    "/api/trigger_event", response_model=GeneralPluginApiResponse, tags=["Plugin API"]
)
async def trigger_event_api_route(
    payload: TriggerEventPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Allows an external source to trigger a custom plugin event within the system.

    Calls :func:`~bedrock_server_manager.api.plugins.trigger_external_plugin_event_api`.
    This can be used for integrations or advanced control flows.

    - **Request body**: Expects a :class:`.TriggerEventPayload` specifying the
      `event_name` and an optional `payload` dictionary for the event.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Custom plugin event '{payload.event_name}' trigger request by '{identity}'."
    )

    try:
        result = plugins_api.trigger_external_plugin_event_api(
            payload.event_name, payload.payload
        )
        if result.get("status") == "success":

            return GeneralPluginApiResponse(
                status="success",
                message=result.get("message"),
                data=result.get("details"),  # API returns 'details', model has 'data'
            )
        else:

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # Or map from result if possible
                detail=result.get("message", "Failed to trigger event."),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Trigger Event '{payload.event_name}': BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
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
    "/api/{plugin_name}", response_model=GeneralPluginApiResponse, tags=["Plugin API"]
)
async def set_plugin_status_api_route(
    plugin_name: str,
    payload: PluginStatusSetPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Sets the enabled or disabled status for a specific plugin.

    Calls :func:`~bedrock_server_manager.api.plugins.set_plugin_status`.
    A plugin reload via :func:`~.reload_plugins_api_route` is typically
    required for the change to take full effect.

    - **plugin_name**: Path parameter specifying the plugin to configure.
    - **Request body**: Expects a :class:`.PluginStatusSetPayload` with the boolean `enabled` field.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    action = "enable" if payload.enabled else "disable"
    logger.info(
        f"API: Request to {action} plugin '{plugin_name}' by user '{identity}'."
    )

    try:
        result = plugins_api.set_plugin_status(plugin_name, payload.enabled)
        if result.get("status") == "success":
            return GeneralPluginApiResponse(
                status="success", message=result.get("message")
            )
        else:
            detail = result.get("message", f"Failed to {action} plugin.")
            if "not found" in detail.lower() or "invalid plugin" in detail.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=detail
                )
            # Other errors from set_plugin_status might be 400 or 500
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail,  # Defaulting to 500
            )

    except UserInputError as e:  # Raised by API if plugin_name is empty or not found
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(f"API Set Plugin '{plugin_name}': BSMError: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Set Plugin '{plugin_name}': Unexpected error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while trying to {action} the plugin.",
        )


@router.put("/api/reload", response_model=GeneralPluginApiResponse, tags=["Plugin API"])
async def reload_plugins_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Triggers a full reload of the plugin system.

    Calls :func:`~bedrock_server_manager.api.plugins.reload_plugins`.
    This involves unloading all current plugins (triggering their `on_unload`
    hooks) and then re-scanning, re-validating, and re-loading all plugins
    based on their current configuration and files on disk.

    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Reload plugins request by '{identity}'.")

    try:
        result = plugins_api.reload_plugins()
        if result.get("status") == "success":
            return GeneralPluginApiResponse(
                status="success", message=result.get("message")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to reload plugins."),
            )
    except BSMError as e:  # reload_plugins might raise BSMError for deeper issues
        logger.error(f"API Reload Plugins: BSMError: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"API Reload Plugins: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while reloading plugins.",
        )
