# bedrock_server_manager/web/routers/account_router.py
"""
FastAPI router for user account management.

This module provides endpoints for:
- Retrieving account details via API.
- Updating user themes.
- Updating profile information (name, email).
- Changing passwords.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ...context import AppContext
from ...db.models import User as UserModel
from ..auth_utils import (
    get_current_user,
    get_password_hash,
    verify_password,
)
from ..dependencies import get_app_context
from ..schemas import (
    BaseApiResponse,
    ChangePasswordPayload,
    ProfileUpdatePayload,
    ThemeUpdatePayload,
    UserResponse,
)

router = APIRouter()


@router.get("/api/account", response_model=UserResponse)
async def account_api(user: UserResponse = Depends(get_current_user)):
    """
    Retrieves the current user's account details.
    """
    return user


@router.post("/api/account/theme", response_model=BaseApiResponse)
async def update_theme(
    theme_update: ThemeUpdatePayload,
    user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Updates the current user's preferred theme.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        db_user = (
            db.query(UserModel).filter(UserModel.username == user.username).first()
        )
        if db_user:
            db_user.theme = theme_update.theme
            db.commit()
            return BaseApiResponse(
                status="success", message="Theme updated successfully"
            )
    return JSONResponse(status_code=404, content={"message": "UserResponse not found"})


@router.post("/api/account/profile", response_model=BaseApiResponse)
async def update_profile(
    profile_update: ProfileUpdatePayload,
    user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Updates the current user's profile information (name, email).
    """
    with app_context.db.session_manager() as db:  # type: ignore
        db_user = (
            db.query(UserModel).filter(UserModel.username == user.username).first()
        )
        if db_user:
            db_user.full_name = profile_update.full_name
            db_user.email = profile_update.email
            db.commit()
            return BaseApiResponse(
                status="success", message="Profile updated successfully"
            )
    return JSONResponse(status_code=404, content={"message": "UserResponse not found"})


@router.post("/api/account/change-password", response_model=BaseApiResponse)
async def change_password(
    data: ChangePasswordPayload,
    user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Changes the current user's password.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        db_user = (
            db.query(UserModel).filter(UserModel.username == user.username).first()
        )
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UserResponse not found.",
            )

        if not verify_password(data.current_password, db_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password.",
            )

        db_user.hashed_password = get_password_hash(data.new_password)
        db.commit()

        return BaseApiResponse(
            status="success", message="Password updated successfully"
        )
