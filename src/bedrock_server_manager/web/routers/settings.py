# bedrock_server_manager/web/routers/settings.py
"""
FastAPI router for managing global application settings.

This module provides endpoints for viewing and modifying the application's
global configuration, typically stored in ``bedrock_server_manager.json``.
It includes:

- An HTML page for users to manage settings (:func:`~.manage_settings_page_route`).
- API endpoints to:
    - Retrieve all current global settings (:func:`~.get_all_settings_api_route`).
    - Set a specific global setting by its key (:func:`~.set_setting_api_route`).
    - Trigger a reload of settings from the configuration file
      (:func:`~.reload_settings_api_route`).

These routes interface with the underlying settings management logic in
:mod:`~bedrock_server_manager.api.settings` and require user authentication.
"""
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import (
    HTMLResponse,
)
from pydantic import BaseModel, Field

from ..schemas import BaseApiResponse
from ..templating import templates
from ..auth_utils import get_current_user
from ...api import settings as settings_api
from ...error import BSMError, UserInputError, MissingArgumentError

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Models ---
class SettingItem(BaseModel):
    """Request model for a single setting key-value pair."""

    key: str = Field(
        ..., description="The dot-notation key of the setting (e.g., 'web.port')."
    )
    value: Any = Field(..., description="The new value for the setting.")


class SettingsResponse(BaseApiResponse):
    """Response model for settings operations."""

    # status: str = Field(...) -> Inherited
    # message: Optional[str] = Field(default=None) -> Inherited
    settings: Optional[Dict[str, Any]] = Field(
        default=None, description="Dictionary of all settings (for get_all)."
    )
    setting: Optional[SettingItem] = Field(
        default=None, description="The specific setting that was acted upon (for set)."
    )


# --- HTML Route: /settings ---
@router.get(
    "/settings",
    response_class=HTMLResponse,
    name="manage_settings_page",
    include_in_schema=False,
)
async def manage_settings_page_route(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Serves the HTML page for managing global application settings.

    This page allows authenticated users to view and modify settings
    stored in the main application configuration file.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
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
    """
    Retrieves all global application settings.

    Calls :func:`~bedrock_server_manager.api.settings.get_all_global_settings`
    to fetch the entire current application configuration.

    - Requires authentication.
    - Returns a :class:`.SettingsResponse` containing all settings data.

    Example Response:
    .. code-block:: json

        {
            "status": "success",
            "message": "Global settings retrieved successfully.",
            "settings": {
                "config_version": "1.0",
                "paths": {
                    "servers": "<app_data_dir>/servers",
                    "content": "<app_data_dir>/content",
                    "downloads": "<app_data_dir>/.downloads",
                    "backups": "<app_data_dir>/backups",
                    "plugins": "<app_data_dir>/plugins",
                    "logs": "<app_data_dir>/.logs"
                },
                "retention": {
                    "backups": 3,
                    "downloads": 3,
                    "logs": 3
                },
                "logging": {
                    "file_level": "INFO",
                    "cli_level": "WARN"
                },
                "web": {
                    "host": "127.0.0.1",
                    "port": 11325,
                    "token_expires_weeks": 4,
                    "threads": 4
                },
                "custom": {}
            },
            "setting": null
        }
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Get global settings request by '{identity}'.")
    try:
        result = settings_api.get_all_global_settings()
        if result.get("status") == "success":
            return SettingsResponse(
                status="success",
                settings=result.get("data"),
                message=result.get("message"),
            )
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
    """
    Sets a specific global application setting.

    Calls :func:`~bedrock_server_manager.api.settings.set_global_setting`
    to update a setting by its dot-notation key and new value.
    Changes are persisted to the configuration file.

    - **Request body**: Expects a :class:`.SettingItem` with the `key` and `value`.
    - Requires authentication.
    - Returns a :class:`.SettingsResponse` indicating success or failure.

    Example Request Body:
    .. code-block:: json

        {
            "key": "retention.backups",
            "value": 5
        }

    Example Response (Success):
    .. code-block:: json

        {
            "status": "success",
            "message": "Setting 'retention.backups' updated successfully. Changes will apply after the next reload or restart.",
            "settings": null,
            "setting": {
                "key": "retention.backups",
                "value": 5
            }
        }
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Set global setting request for key '{payload.key}' by '{identity}'."
    )

    if not payload.key:  # Redundant due to Pydantic Field(...) validation
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
                setting=SettingItem(
                    key=payload.key, value=payload.value
                ),  # Return the set item - No change needed here as it already matches BaseApiResponse for status/message
            )
        else:
            # Errors from settings_api.set_global_setting should ideally raise specific BSMError types
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,  # Or 500 if it's a save error
                detail=result.get("message", "Failed to set setting."),
            )
    except (
        UserInputError,
        MissingArgumentError,
    ) as e:  # These might be raised by settings_api or earlier checks
        logger.warning(f"API Set Setting '{payload.key}': Input error. {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:  # Catch other BSM specific errors (e.g., ConfigWriteError)
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
    """
    Forces a reload of global application settings and logging configuration.

    Calls :func:`~bedrock_server_manager.api.settings.reload_global_settings`.
    This is useful if the configuration file has been manually edited and the
    application needs to reflect these changes without a full restart.

    - Requires authentication.
    - Returns a :class:`.SettingsResponse` indicating the outcome.

    Example Response:
    .. code-block:: json

        {
            "status": "success",
            "message": "Global settings and logging configuration reloaded successfully.",
            "settings": null,
            "setting": null
        }
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Reload global settings request by '{identity}'.")
    try:
        result = settings_api.reload_global_settings()
        if result.get("status") == "success":
            return SettingsResponse(
                status="success",
                message=result.get("message", "Settings reloaded successfully."),
                # No other specific fields like 'settings' or 'setting' for this response
            )
        else:
            # Errors from settings_api.reload_global_settings
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to reload settings."),
            )
    except BSMError as e:  # E.g. ConfigLoadError
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
