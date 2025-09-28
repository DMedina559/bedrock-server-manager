import os
from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from bedrock_server_manager.web.auth_utils import (
    get_current_user,
    verify_password,
    get_password_hash,
)
from fastapi.templating import Jinja2Templates

from bedrock_server_manager.db.models import User as UserModel
from ..dependencies import get_templates, get_app_context
from pydantic import BaseModel
from ..schemas import User as UserSchema, BaseApiResponse
from ...context import AppContext

router = APIRouter()


class ThemeUpdate(BaseModel):
    theme: str


class ProfileUpdate(BaseModel):
    full_name: str
    email: str


class ChangePasswordRequest(BaseModel):
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
    return templates.TemplateResponse(request, "account.html", {"current_user": user})


@router.get("/api/account", response_model=UserSchema)
async def account_api(user: UserSchema = Depends(get_current_user)):
    return user


@router.post("/api/account/theme", response_model=BaseApiResponse)
async def update_theme(
    theme_update: ThemeUpdate,
    user: UserSchema = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
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
