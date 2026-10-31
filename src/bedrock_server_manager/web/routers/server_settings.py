"""
FastAPI router for managing server-specific settings.
"""

import logging

from fastapi import APIRouter, Depends, Security

from ...api import server as server_api
from ...api.models import GetAllServerSettingsRequest, SetServerSettingRequest
from ...context import AppContext
from ..access_policy import Permission
from ..deps import get_app_context, validate_server_exists
from ..deps.auth import require_permissions
from ..schemas import ServerSettingItemPayload, ServerSettingsResponse, UserResponse

# bedrock_server_manager/web/routers/server_settings.py


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Server Settings"])


# --- API Route: Get All Settings for a Server ---
@router.get(
    "/api/server/{server_name}/settings/get",
    operation_id="get_server_settings",
    response_model=ServerSettingsResponse,
)
async def get_server_settings(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> ServerSettingsResponse:
    """Return all settings for a specific server."""
    identity = current_user.username
    logger.debug("Get settings for server '%s' request by '%s'.", server_name, identity)
    result = await server_api.get_all_server_settings(
        request=GetAllServerSettingsRequest(server_name=server_name),
        app_context=app_context,
    )
    return ServerSettingsResponse(
        status="success",
        settings=result.settings,
        message=f"Successfully retrieved settings for server '{server_name}'.",
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
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_CONFIGURE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> ServerSettingsResponse:
    """Set a specific setting for a server."""
    identity = current_user.username
    logger.info(
        "Set setting for server '%s' request for key '%s' by '%s'.",
        server_name,
        payload.key,
        identity,
    )
    result = await server_api.set_server_setting(
        request=SetServerSettingRequest(
            server_name=server_name, key=payload.key, value=payload.value
        ),
        app_context=app_context,
    )
    return ServerSettingsResponse(
        status=result.status,
        message=f"Setting '{payload.key}' updated successfully for server '{server_name}'.",
        setting=payload,
    )
