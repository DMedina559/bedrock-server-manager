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
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetAllGlobalSettingsRequest,
    ReloadGlobalSettingsRequest,
    SetGlobalSettingRequest,
)

from ...api import settings as settings_api
from ...context import AppContext
from ...error import (
    AppFileNotFoundError,
    BSMError,
    MissingArgumentError,
    UserInputError,
)
from ...logging import log_operation_error
from ..deps import get_admin_user, get_app_context
from ..schemas import SettingItemResponse, SettingsResponse, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Application Settings"])


# --- API Route: Get All Global Settings ---
@router.get(
    "/api/settings/get",
    operation_id="get_settings",
    response_model=SettingsResponse,
)
async def get_all_settings(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> SettingsResponse:
    """
    Retrieves all global application settings.
    """
    identity = current_user.username
    logger.debug("Get global settings request by '%s'.", identity)
    try:
        result = await settings_api.get_all_global_settings(
            request=GetAllGlobalSettingsRequest(), app_context=app_context
        )
        return SettingsResponse(
            status="success",
            settings=result.settings,
            message=result.message,
        )
    except HTTPException:
        raise
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "API Get Settings: Unexpected error. %s", e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving settings.",
        )


# --- API Route: Set a Global Setting ---
@router.post(
    "/api/settings/set",
    operation_id="set_setting",
    response_model=SettingsResponse,
)
async def post_set_setting(
    payload: SettingItemResponse,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> SettingsResponse:
    """
    Sets a specific global application setting.
    """
    identity = current_user.username
    logger.info(
        "Set global setting request for key '%s' by '%s'.", payload.key, identity
    )
    if not payload.key:  # Redundant due to Pydantic Field(...) validation
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setting 'key' cannot be empty.",
        )

    try:

        result = await settings_api.set_global_setting(
            request=SetGlobalSettingRequest(key=payload.key, value=payload.value),
            app_context=app_context,
        )
        return SettingsResponse(
            status=result.status,
            message=result.message,
            setting=SettingItemResponse(
                key=payload.key, value=payload.value
            ),  # Return the set item - No change needed here as it already matches BaseApiResponse for status/message
        )
    except (
        UserInputError,
        MissingArgumentError,
    ) as e:  # These might be raised by settings_api or earlier checks
        logger.debug("API Set Setting '%s': Input error. %s", payload.key, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except AppFileNotFoundError:
        raise
    except BSMError as e:  # Catch other BSM specific errors (e.g., ConfigWriteError)
        logger.debug(
            "API Set Setting '%s': BSMError. %s", payload.key, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "API Set Setting '%s': Unexpected error. %s",
            payload.key,
            e,
            error=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while setting the value.",
        )


# --- API Route: Reload Global Settings ---
@router.put(
    "/api/settings/reload",
    operation_id="reload_settings",
    response_model=SettingsResponse,
)
async def put_reload_settings(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> SettingsResponse:
    """
    Forces a reload of global application settings and logging configuration.
    """
    identity = current_user.username
    logger.info("Reload global settings request by '%s'.", identity)
    try:
        result = await settings_api.reload_global_settings(
            request=ReloadGlobalSettingsRequest(), app_context=app_context
        )
        return SettingsResponse(
            status=result.status,
            message=result.message,
            # No other specific fields like 'settings' or 'setting' for this response
        )
    except HTTPException:
        raise
    except AppFileNotFoundError:
        raise
    except BSMError as e:  # E.g. ConfigLoadError
        logger.debug("API Reload Settings: BSMError. %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "API Reload Settings: Unexpected error. %s", e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while reloading settings.",
        )
