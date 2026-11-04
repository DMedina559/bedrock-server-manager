"""FastAPI router for managing global application settings."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Security

from ...api import settings as settings_api
from ...context import AppContext
from ...models import (
    GetAllGlobalSettingsRequest,
    GetAllGlobalSettingsResponse,
    ReloadGlobalSettingsRequest,
    ReloadGlobalSettingsResponse,
    SetGlobalSettingRequest,
    SetGlobalSettingResponse,
    SettingItemPayload,
)
from ..access_metadata import describe_access
from ..access_policy import Permission
from ..deps import get_app_context
from ..deps.auth import require_permissions, require_recent_interactive
from ..schemas import UserResponse

# bedrock_server_manager/web/routers/settings.py


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Application Settings"])


# --- API Route: Get All Global Settings ---
@router.get(
    "/api/settings/get",
    operation_id="get_settings",
    response_model=GetAllGlobalSettingsResponse,
)
async def get_all_settings(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SETTINGS_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> GetAllGlobalSettingsResponse:
    """Return all global application settings."""
    identity = current_user.username
    logger.debug("Get global settings request by '%s'.", identity)
    result = await settings_api.get_all_global_settings(
        request=GetAllGlobalSettingsRequest(), app_context=app_context
    )
    public = dict(result.settings)
    public.pop("plugin_settings", None)
    web = public.get("web", {})
    public["web"] = {
        k: v
        for k, v in (web.items() if isinstance(web, dict) else [])
        if k not in {"jwt_secret_key", "jwt_key_initialized"}
    }
    return GetAllGlobalSettingsResponse(
        status="success",
        settings=public,
        message=result.message,
    )


# --- API Route: Set a Global Setting ---
@router.post(
    "/api/settings/set",
    operation_id="set_setting",
    response_model=SetGlobalSettingResponse,
)
@describe_access(
    "permission",
    additional_checks=["recent-interactive-verification"],
)
async def post_set_setting(
    payload: SettingItemPayload,
    request: Request,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SETTINGS_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> SetGlobalSettingResponse:
    """Set a specific global application setting."""
    await require_recent_interactive(request, current_user, app_context)
    identity = current_user.username
    logger.info(
        "Set global setting request for key '%s' by '%s'.", payload.key, identity
    )

    root = payload.key.split(".")[0]
    state = app_context.state.settings
    plugin_alias = (
        root not in type(state).model_fields
        and root not in state.custom
        and root in state.plugin_settings
    )
    if (
        payload.key == "plugin_settings"
        or payload.key.startswith("plugin_settings.")
        or plugin_alias
    ):
        raise HTTPException(
            403, "Use the plugin settings endpoint for plugin-owned settings."
        )
    return await settings_api.set_global_setting(
        request=SetGlobalSettingRequest(key=payload.key, value=payload.value),
        app_context=app_context,
    )


# --- API Route: Reload Global Settings ---
@router.put(
    "/api/settings/reload",
    operation_id="reload_settings",
    response_model=ReloadGlobalSettingsResponse,
)
async def put_reload_settings(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SETTINGS_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> ReloadGlobalSettingsResponse:
    """
    Forces a reload of global application settings and logging configuration.
    """
    identity = current_user.username
    logger.info("Reload global settings request by '%s'.", identity)
    return await settings_api.reload_global_settings(
        request=ReloadGlobalSettingsRequest(), app_context=app_context
    )
