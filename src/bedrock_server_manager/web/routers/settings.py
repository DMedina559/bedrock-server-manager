import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from bedrock_server_manager.web.templating import templates
from bedrock_server_manager.web.auth_utils import get_current_user
from bedrock_server_manager.api import settings as settings_api
from bedrock_server_manager.error import BSMError, UserInputError, MissingArgumentError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Global Settings"])


# --- Pydantic Models ---
class SettingItem(BaseModel):
    key: str
    value: Any


class SettingsResponse(BaseModel):
    status: str
    message: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    setting: Optional[SettingItem] = None


# --- HTML Route: /settings ---
@router.get("/settings", response_class=HTMLResponse, name="manage_settings_page")
async def manage_settings_page_route(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user)
):
    identity = current_user.get("username", "Unknown")
    logger.info(f"User '{identity}' accessed global settings page.")
    return templates.TemplateResponse(
        "manage_settings.html", {"request": request, "current_user": current_user}
    )


# --- API Route: Get All Global Settings ---
@router.get("/api/settings", response_model=SettingsResponse, tags=["Settings API"])
async def get_all_settings_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Get global settings request by '{identity}'.")
    try:
        result = settings_api.get_all_global_settings()
        if result.get("status") == "success":
            return SettingsResponse(status="success", settings=result.get("settings"))
        else:
            # This case might indicate an internal issue with settings loading
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to retrieve settings."),
            )
    except Exception as e:
        logger.error(f"API Get Settings: Unexpected error. {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving settings.",
        )


# --- API Route: Set a Global Setting ---
@router.post("/api/settings", response_model=SettingsResponse, tags=["Settings API"])
async def set_setting_api_route(
    payload: SettingItem,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Set global setting request for key '{payload.key}' by '{identity}'."
    )

    if not payload.key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setting 'key' cannot be empty.",
        )

    try:

        result = settings_api.set_global_setting(payload.key, payload.value)
        if result.get("status") == "success":

            return SettingsResponse(
                status="success",
                message=result.get("message", "Setting updated successfully."),
                setting=SettingItem(key=payload.key, value=payload.value),
            )
        else:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Failed to set setting."),
            )
    except (UserInputError, MissingArgumentError) as e:
        logger.warning(f"API Set Setting '{payload.key}': Input error. {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(f"API Set Setting '{payload.key}': BSMError. {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Set Setting '{payload.key}': Unexpected error. {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while setting the value.",
        )


# --- API Route: Reload Global Settings ---
@router.post(
    "/api/settings/reload", response_model=SettingsResponse, tags=["Settings API"]
)
async def reload_settings_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Reload global settings request by '{identity}'.")
    try:
        result = settings_api.reload_global_settings()
        if result.get("status") == "success":
            return SettingsResponse(
                status="success",
                message=result.get("message", "Settings reloaded successfully."),
            )
        else:

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to reload settings."),
            )
    except BSMError as e:
        logger.error(f"API Reload Settings: BSMError. {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"API Reload Settings: Unexpected error. {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while reloading settings.",
        )
