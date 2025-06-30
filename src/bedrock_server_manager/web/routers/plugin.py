import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Request as FastAPIRequest
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
    enabled: bool


class TriggerEventPayload(BaseModel):
    event_name: str = Field(..., min_length=1)
    payload: Optional[Dict[str, Any]] = None


class GeneralPluginApiResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Any] = None


# --- HTML Route ---
@router.get("/", response_class=HTMLResponse, name="manage_plugins_page")
async def manage_plugins_page_route(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user)
):
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
    "/api/{plugin_name}", response_model=GeneralPluginApiResponse, tags=["Plugin API"]
)
async def set_plugin_status_api_route(
    plugin_name: str,
    payload: PluginStatusSetPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
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
    "/api/reload", response_model=GeneralPluginApiResponse, tags=["Plugin API"]
)
async def reload_plugins_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
