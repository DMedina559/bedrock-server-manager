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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ...api import plugins as plugins_api
from ...context import AppContext
from ...error import BSMError, UserInputError
from ...plugins.plugin_manager import PluginManager
from ..auth_utils import get_admin_user, get_current_user
from ..dependencies import get_app_context, get_templates
from ..schemas import BaseApiResponse, User

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Models ---
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


class PluginApiResponse(BaseApiResponse):
    """Generic API response model for plugin operations."""

    # status: str -> Inherited
    # message: Optional[str] = None -> Inherited
    data: Optional[Any] = Field(
        default=None,
        description="Optional data payload, structure depends on the endpoint (e.g., plugin statuses).",
    )


# --- HTML Route ---
@router.get(
    "/plugins",
    response_class=HTMLResponse,
    name="manage_plugins_page",
    include_in_schema=False,
)
async def manage_plugins_page_route(
    request: Request,
    current_user: User = Depends(get_admin_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for managing installed plugins.
    """
    identity = current_user.username
    logger.info(f"User '{identity}' accessed plugin management page.")
    return templates.TemplateResponse(
        request,
        "manage_plugins.html",
        {"current_user": current_user},
    )


# --- API Route ---
@router.get("/api/plugins", response_model=PluginApiResponse, tags=["Plugin API"])
async def get_plugins_status_api_route(
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the statuses and metadata of all discovered plugins.
    """
    identity = current_user.username
    logger.info(f"API: Get plugin statuses request by '{identity}'.")
    try:
        result = plugins_api.get_plugin_statuses(app_context=app_context)
        if result.get("status") == "success":
            return PluginApiResponse(status="success", data=result.get("plugins"))
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


@router.post(
    "/api/plugins/trigger_event",
    response_model=PluginApiResponse,
    tags=["Plugin API"],
)
async def trigger_event_api_route(
    payload: TriggerEventPayload,
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Allows an external source to trigger a custom plugin event within the system.
    """
    identity = current_user.username
    logger.info(
        f"API: Custom plugin event '{payload.event_name}' trigger request by '{identity}'."
    )

    try:
        result = plugins_api.trigger_external_plugin_event_api(
            app_context=app_context,
            event_name=payload.event_name,
            payload=payload.payload,
        )
        if result.get("status") == "success":
            return PluginApiResponse(
                status="success",
                message=result.get("message"),
                data=result.get("details"),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
    "/api/plugins/{plugin_name}",
    response_model=PluginApiResponse,
    tags=["Plugin API"],
)
async def set_plugin_status_api_route(
    plugin_name: str,
    payload: PluginStatusSetPayload,
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Sets the enabled or disabled status for a specific plugin.
    """
    identity = current_user.username
    action = "enable" if payload.enabled else "disable"
    logger.info(
        f"API: Request to {action} plugin '{plugin_name}' by user '{identity}'."
    )

    try:
        result = plugins_api.set_plugin_status(
            app_context=app_context, plugin_name=plugin_name, enabled=payload.enabled
        )
        if result.get("status") == "success":
            return PluginApiResponse(status="success", message=result.get("message"))
        else:
            detail = result.get("message", f"Failed to {action} plugin.")
            if "not found" in detail.lower() or "invalid plugin" in detail.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=detail
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail,
            )

    except UserInputError as e:
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


@router.put(
    "/api/plugins/reload", response_model=PluginApiResponse, tags=["Plugin API"]
)
async def reload_plugins_api_route(
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Triggers a full reload of the plugin system.
    """
    identity = current_user.username
    logger.info(f"API: Reload plugins request by '{identity}'.")

    try:
        result = plugins_api.reload_plugins(app_context=app_context)
        if result.get("status") == "success":
            return PluginApiResponse(status="success", message=result.get("message"))
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to reload plugins."),
            )
    except BSMError as e:
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
