# bedrock_server_manager/web/routers/account_router.py
"""
FastAPI router for user account management.

This module provides endpoints for:
- Viewing the account profile page.
- Retrieving account details via API.
- Updating user themes.
- Updating profile information (name, email).
- Changing passwords.
"""
import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.web.auth_utils import (
    get_current_user,
    get_password_hash,
    verify_password,
)

from ...context import AppContext
from ..dependencies import get_app_context, get_templates
from ..schemas import BaseApiResponse
from ..schemas import User as UserSchema

router = APIRouter()


class ThemeUpdate(BaseModel):
    """
    Request payload for updating the user's theme.

    Attributes:
        theme (str): The new theme name.
    """

    theme: str


class ProfileUpdate(BaseModel):
    """
    Request payload for updating user profile details.

    Attributes:
        full_name (str): The user's full name.
        email (str): The user's email address.
    """

    full_name: str
    email: str


class ChangePasswordRequest(BaseModel):
    """
    Request payload for changing the user's password.

    Attributes:
        current_password (str): The current password for verification.
        new_password (str): The new password.
    """

    current_password: str
    new_password: str


@router.get(
    "/account",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def account_page(
    request: Request,
    user: UserSchema = Depends(get_current_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the user account profile page.
    """
    return templates.TemplateResponse(request, "account.html", {"current_user": user})


@router.get("/api/account", response_model=UserSchema)
async def account_api(user: UserSchema = Depends(get_current_user)):
    """
    Retrieves the current user's account details.
    """
    return user


@router.post("/api/account/theme", response_model=BaseApiResponse)
async def update_theme(
    theme_update: ThemeUpdate,
    user: UserSchema = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Updates the current user's preferred theme.
    """
    with app_context.db.session_manager() as db:
        db_user = (
            db.query(UserModel).filter(UserModel.username == user.username).first()
        )
        if db_user:
            db_user.theme = theme_update.theme
            db.commit()
            return BaseApiResponse(
                status="success", message="Theme updated successfully"
            )
    return JSONResponse(status_code=404, content={"message": "User not found"})


@router.post("/api/account/profile", response_model=BaseApiResponse)
async def update_profile(
    profile_update: ProfileUpdate,
    user: UserSchema = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Updates the current user's profile information (name, email).
    """
    with app_context.db.session_manager() as db:
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
    return JSONResponse(status_code=404, content={"message": "User not found"})


@router.post("/api/account/change-password", response_model=BaseApiResponse)
async def change_password(
    data: ChangePasswordRequest,
    user: UserSchema = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Changes the current user's password.
    """
    with app_context.db.session_manager() as db:
        db_user = (
            db.query(UserModel).filter(UserModel.username == user.username).first()
        )
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
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
