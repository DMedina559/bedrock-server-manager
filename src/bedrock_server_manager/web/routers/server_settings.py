# bedrock_server_manager/web/routers/server_settings.py
"""
FastAPI router for managing server-specific settings.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from ...context import AppContext
from ...error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
    UserInputError,
)
from ...logging import log_operation_error
from ..deps import (
    get_admin_user,
    get_app_context,
    get_current_user,
    validate_server_exists,
)
from ..schemas import ServerSettingItemPayload, ServerSettingsResponse, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Server Settings"],
)


# --- API Route: Get All Settings for a Server ---
@router.get(
    "/api/server/{server_name}/settings/get",
    operation_id="get_server_settings",
    response_model=ServerSettingsResponse,
)
async def get_server_settings(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> ServerSettingsResponse:
    """
    Retrieves all settings for a specific server.
    """
    identity = current_user.username
    logger.debug("Get settings for server '%s' request by '%s'.", server_name, identity)
    try:
        server = app_context.get_server(server_name)
        config = server.configuration.as_settings()
        return ServerSettingsResponse(
            status="success",
            settings=config,
            message=f"Successfully retrieved settings for server '{server_name}'.",
        )
    except HTTPException:
        raise
    except InvalidServerNameError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found.",
        )
    except Exception as e:
        log_operation_error(
            logger, "API Get Server Settings: Unexpected error. %s", e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving server settings.",
        )


# --- API Route: Set a Setting for a Server ---
@router.post(
    "/api/server/{server_name}/settings/set",
    operation_id="set_server_setting",
    response_model=ServerSettingsResponse,
)
async def post_set_server_setting(
    payload: ServerSettingItemPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> ServerSettingsResponse:
    """
    Sets a specific setting for a server.
    """
    identity = current_user.username
    logger.info(
        "Set setting for server '%s' request for key '%s' by '%s'.",
        server_name,
        payload.key,
        identity,
    )
    try:
        server = app_context.get_server(server_name)
        await server.configuration.update(payload.key, payload.value)
        return ServerSettingsResponse(
            status="success",
            message=f"Setting '{payload.key}' updated successfully for server '{server_name}'.",
            setting=payload,
        )
    except HTTPException:
        raise
    except InvalidServerNameError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found.",
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422, detail="Invalid server setting value."
        ) from error
    except (UserInputError, MissingArgumentError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        log_operation_error(
            logger, "API Set Server Setting: Unexpected error. %s", e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while setting the server value.",
        )
