# bedrock_server_manager/web/routers/settings.py
"""
FastAPI router for managing global application settings.

This module provides endpoints for viewing and modifying the application's
global configuration, typically stored in ``bedrock_server_manager.json``.
It includes:

- API endpoints to:
    - Retrieve all current global settings (:func:`~.get_all_settings_api_route`).
    - Set a specific global setting by its key (:func:`~.set_setting_api_route`).
    - Trigger a reload of settings from the configuration file
      (:func:`~.reload_settings_api_route`).

These routes interface with the underlying settings management logic in
:mod:`~bedrock_server_manager.api.settings` and require user authentication.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ...api import settings as settings_api
from ...context import AppContext
from ...error import BSMError, MissingArgumentError, UserInputError
from ..deps import get_admin_user, get_app_context
from ..schemas import SettingItemResponse, SettingsResponse, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Application Settings"])


# --- API Route: Get All Global Settings ---
@router.get(
    "/api/settings/get",
    response_model=SettingsResponse,
)
async def get_all_settings(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves all global application settings.
    """
    identity = current_user.username
    logger.info(f"API: Get global settings request by '{identity}'.")
    try:
        result = settings_api.get_all_global_settings(app_context=app_context)
        if result.get("status") == "success":
            return SettingsResponse(
                status="success",
                settings={
                    k: v for k, v in result.items() if k not in ("status", "message")
                },
                message=result.get("message"),
            )
        else:
            # This case might indicate an internal issue with settings loading
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to retrieve settings."),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API Get Settings: Unexpected error. {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving settings.",
        )


# --- API Route: Set a Global Setting ---
@router.post(
    "/api/settings/set",
    response_model=SettingsResponse,
)
async def post_set_setting(
    payload: SettingItemResponse,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Sets a specific global application setting.
    """
    identity = current_user.username
    logger.info(
        f"API: Set global setting request for key '{payload.key}' by '{identity}'."
    )
    if not payload.key:  # Redundant due to Pydantic Field(...) validation
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setting 'key' cannot be empty.",
        )

    try:

        result = settings_api.set_global_setting(
            key=payload.key, value=payload.value, app_context=app_context
        )
        if result.get("status") == "success":

            return SettingsResponse(
                status="success",
                message=result.get("message", "Setting updated successfully."),
                setting=SettingItemResponse(
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
    except HTTPException:
        raise
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
@router.put("/api/settings/reload", response_model=SettingsResponse)
async def put_reload_settings(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Forces a reload of global application settings and logging configuration.
    """
    identity = current_user.username
    logger.info(f"API: Reload global settings request by '{identity}'.")
    try:
        result = settings_api.reload_global_settings(app_context=app_context)
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
    except HTTPException:
        raise
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
