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
async def get_account_api(user: UserResponse = Depends(get_current_user)):
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
):
    """
    Updates the current user's preferred theme.
    """
    # Match apply_changeset's lock order so a pending flush cannot restore
    # the old cached theme after this database write.
    async with app_context.storage._flush_lock:
        async with app_context.state.users.get_lock(user.username):
            async with app_context.storage.transaction() as session:
                db_user: Any = await app_context.storage.user_repo.get_user_by_username(
                    session, user.username
                )
                if not db_user:
                    return JSONResponse(
                        status_code=404, content={"message": "UserResponse not found"}
                    )
                db_user.theme = theme_update.theme

            # Publish only after commit succeeds. Preserve pending edits to other
            # account fields and their dirty flag.
            cached_user = app_context.state.users.get(user.username)
            if cached_user is not None:
                was_dirty = user.username in app_context.state.users.dirty_users
                cached_user.theme = theme_update.theme
                app_context.state.users.set(cached_user)
                if not was_dirty:
                    app_context.state.users.remove_dirty_user(user.username)

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
):
    """
    Updates the current user's profile information (name, email).
    """
    async with app_context.storage.transaction() as session:
        db_user: Any = await app_context.storage.user_repo.get_user_by_username(
            session, user.username
        )
        if db_user:
            db_user.full_name = profile_update.full_name
            db_user.email = profile_update.email
            return BaseApiResponse(
                status="success", message="Profile updated successfully"
            )
    return JSONResponse(status_code=404, content={"message": "UserResponse not found"})


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
):
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
