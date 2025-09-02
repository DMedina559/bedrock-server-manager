# bedrock_server_manager/web/routers/server_settings.py
"""
FastAPI router for managing server-specific settings.
"""
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Path
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from fastapi.templating import Jinja2Templates

from ..schemas import BaseApiResponse, User
from ..dependencies import get_templates, get_app_context
from ..auth_utils import get_current_user, get_admin_user
from ...error import (
    BSMError,
    UserInputError,
    MissingArgumentError,
    InvalidServerNameError,
)
from ...context import AppContext

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Models ---
class ServerSettingItem(BaseModel):
    """Request model for a single server setting key-value pair."""

    key: str = Field(
        ...,
        description="The dot-notation key of the setting (e.g., 'settings.autoupdate').",
    )
    value: Any = Field(..., description="The new value for the setting.")


class ServerSettingsResponse(BaseApiResponse):
    """Response model for server settings operations."""

    settings: Optional[Dict[str, Any]] = Field(
        default=None, description="Dictionary of all settings."
    )
    setting: Optional[ServerSettingItem] = Field(
        default=None, description="The specific setting that was acted upon."
    )


# --- API Route: Get All Settings for a Server ---
@router.get(
    "/api/servers/{server_name}/settings",
    response_model=ServerSettingsResponse,
    tags=["Server Settings API"],
)
async def get_server_settings_api_route(
    server_name: str = Path(..., description="The name of the server."),
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves all settings for a specific server.
    """
    identity = current_user.username
    logger.info(
        f"API: Get settings for server '{server_name}' request by '{identity}'."
    )
    try:
        server = app_context.get_server(server_name)
        config = server._load_server_config()
        return ServerSettingsResponse(
            status="success",
            settings=config,
            message=f"Successfully retrieved settings for server '{server_name}'.",
        )
    except InvalidServerNameError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found.",
        )
    except Exception as e:
        logger.error(f"API Get Server Settings: Unexpected error. {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving server settings.",
        )


# --- API Route: Set a Setting for a Server ---
@router.post(
    "/api/servers/{server_name}/settings",
    response_model=ServerSettingsResponse,
    tags=["Server Settings API"],
)
async def set_server_setting_api_route(
    payload: ServerSettingItem,
    server_name: str = Path(..., description="The name of the server."),
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Sets a specific setting for a server.
    """
    identity = current_user.username
    logger.info(
        f"API: Set setting for server '{server_name}' request for key '{payload.key}' by '{identity}'."
    )
    try:
        server = app_context.get_server(server_name)
        server._manage_json_config(
            key=payload.key, operation="write", value=payload.value
        )
        return ServerSettingsResponse(
            status="success",
            message=f"Setting '{payload.key}' updated successfully for server '{server_name}'.",
            setting=payload,
        )
    except InvalidServerNameError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found.",
        )
    except (UserInputError, MissingArgumentError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"API Set Server Setting: Unexpected error. {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while setting the server value.",
        )
