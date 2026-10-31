"""
FastAPI router for user account management.

This module provides endpoints for:
- Retrieving account details via API.
- Updating user themes.
- Updating profile information (name, email).
- Changing passwords.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.responses import JSONResponse

from ...context import AppContext
from ...state.updates import AccountPatch
from ..access_policy import Permission, policy_for
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import (
    BaseApiResponse,
    ChangePasswordPayload,
    ProfileUpdatePayload,
    ThemeUpdatePayload,
    UserResponse,
)
from ..schemas.users import CurrentAccountResponse

# bedrock_server_manager/web/routers/account_router.py


router = APIRouter(tags=["Account Management"])


@router.get(
    "/api/account", operation_id="get_account", response_model=CurrentAccountResponse
)
async def get_account_api(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCOUNT_READ]
    ),
) -> CurrentAccountResponse:
    """Return the current user's account details and role-derived permissions."""
    return CurrentAccountResponse(
        **user.model_dump(), permissions=sorted(policy_for(request).resolve(user.role))
    )


@router.post(
    "/api/account/theme",
    operation_id="update_account_theme",
    response_model=BaseApiResponse,
)
async def post_update_theme(
    theme_update: ThemeUpdatePayload,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCOUNT_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse | JSONResponse:
    """
    Updates the current user's preferred theme.
    """
    result = await app_context.user_service.update_account(
        action="theme",
        username=user.username,
        values=AccountPatch(theme=theme_update.theme),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="User not found.")

    return BaseApiResponse(status="success", message="Theme updated successfully")


@router.post(
    "/api/account/profile",
    operation_id="update_account_profile",
    response_model=BaseApiResponse,
)
async def post_update_profile(
    profile_update: ProfileUpdatePayload,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCOUNT_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse | JSONResponse:
    """
    Updates the current user's profile information (name, email).
    """
    result = await app_context.user_service.update_account(
        action="profile",
        username=user.username,
        values=AccountPatch.model_validate(
            profile_update.model_dump(exclude_unset=True)
        ),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return BaseApiResponse(status="success", message="Profile updated successfully")


@router.post(
    "/api/account/change-password",
    operation_id="change_password",
    response_model=BaseApiResponse,
)
async def post_change_password(
    data: ChangePasswordPayload,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCOUNT_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    """
    Changes the current user's password.
    """
    updated = await app_context.user_service.change_password(
        user.username,
        data.current_password.get_secret_value(),
        data.new_password.get_secret_value(),
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return BaseApiResponse(status="success", message="Password updated successfully")


@router.get(
    "/api/account/permissions",
    operation_id="get_account_permissions",
    response_model=list[str],
)
async def get_account_permissions(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCOUNT_READ]
    ),
) -> list[str]:
    """Return current role-derived capabilities, not resource-specific guarantees."""
    return sorted(policy_for(request).resolve(user.role))
