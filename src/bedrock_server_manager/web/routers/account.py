# bedrock_server_manager/web/routers/account_router.py
"""
FastAPI router for user account management.

This module provides endpoints for:
- Retrieving account details via API.
- Updating user themes.
- Updating profile information (name, email).
- Changing passwords.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ...context import AppContext
from ...utils import (
    get_password_hash,
    verify_password,
)
from ..deps import get_app_context, get_current_user
from ..schemas import (
    BaseApiResponse,
    ChangePasswordPayload,
    ProfileUpdatePayload,
    ThemeUpdatePayload,
    UserResponse,
)

router = APIRouter(
    tags=["Account Management"],
)


@router.get("/api/account", operation_id="get_account", response_model=UserResponse)
async def get_account_api(
    user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """
    Retrieves the current user's account details.
    """
    return user


@router.post(
    "/api/account/theme",
    operation_id="update_account_theme",
    response_model=BaseApiResponse,
    tags=["Themes"],
)
async def post_update_theme(
    theme_update: ThemeUpdatePayload,
    user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse | JSONResponse:
    """
    Updates the current user's preferred theme.
    """
    result = await app_context.user_service.update_account(
        action="theme", username=user.username, values={"theme": theme_update.theme}
    )
    if result is None:
        return JSONResponse(status_code=404, content={"message": "User not found"})

    return BaseApiResponse(status="success", message="Theme updated successfully")


@router.post(
    "/api/account/profile",
    operation_id="update_account_profile",
    response_model=BaseApiResponse,
)
async def post_update_profile(
    profile_update: ProfileUpdatePayload,
    user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse | JSONResponse:
    """
    Updates the current user's profile information (name, email).
    """
    result = await app_context.user_service.update_account(
        action="profile",
        username=user.username,
        values=profile_update.model_dump(),
    )
    if result is None:
        return JSONResponse(status_code=404, content={"message": "User not found"})
    return BaseApiResponse(status="success", message="Profile updated successfully")


@router.post(
    "/api/account/change-password",
    operation_id="change_password",
    response_model=BaseApiResponse,
    tags=["Password", "Authentication"],
)
async def post_change_password(
    data: ChangePasswordPayload,
    user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    """
    Changes the current user's password.
    """
    async with app_context.storage.transaction() as session:
        db_user: Any = await app_context.storage.user_repo.get_user_by_username(
            session, user.username
        )
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UserResponse not found.",
            )

        if not verify_password(data.current_password, str(db_user.hashed_password)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password.",
            )

        db_user.hashed_password = get_password_hash(data.new_password)

        return BaseApiResponse(
            status="success", message="Password updated successfully"
        )
