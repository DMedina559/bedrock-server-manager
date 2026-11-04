"""
FastAPI router for managing server-specific settings.
"""

import logging

from fastapi import APIRouter, Depends, Security

from ...api import server as server_api
from ...context import AppContext
from ...models import (
    GetAllServerSettingsRequest,
    GetAllServerSettingsResponse,
    ServerSettingItemPayload,
    SetServerSettingRequest,
    SetServerSettingResponse,
)
from ..access_policy import Permission
from ..deps import get_app_context, validate_server_exists
from ..deps.auth import require_permissions
from ..schemas import UserResponse

# bedrock_server_manager/web/routers/server_settings.py


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Server Settings"])


# --- API Route: Get All Settings for a Server ---
@router.get(
    "/api/server/{server_name}/settings/get",
    operation_id="get_server_settings",
    response_model=GetAllServerSettingsResponse,
)
async def get_server_settings(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_READ]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> GetAllServerSettingsResponse:
    """Return all settings for a specific server."""
    identity = current_user.username
    logger.debug("Get settings for server '%s' request by '%s'.", server_name, identity)
    return await server_api.get_all_server_settings(
        request=GetAllServerSettingsRequest(server_name=server_name),
        app_context=app_context,
    )


# --- API Route: Set a Setting for a Server ---
@router.post(
    "/api/server/{server_name}/settings/set",
    operation_id="set_server_setting",
    response_model=SetServerSettingResponse,
)
async def post_set_server_setting(
    payload: ServerSettingItemPayload,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_CONFIGURE]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> SetServerSettingResponse:
    """Set a specific setting for a server."""
    identity = current_user.username
    logger.info(
        "Set setting for server '%s' request for key '%s' by '%s'.",
        server_name,
        payload.key,
        identity,
    )
    return await server_api.set_server_setting(
        request=SetServerSettingRequest(
            server_name=server_name, key=payload.key, value=payload.value
        ),
        app_context=app_context,
    )
