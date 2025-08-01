import os
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from bedrock_server_manager.web.auth_utils import get_current_user
from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.db.database import db_session_manager
from ..templating import templates
from pydantic import BaseModel
from ..schemas import User as UserSchema, BaseApiResponse

router = APIRouter()


class ThemeUpdate(BaseModel):
    theme: str


@router.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, user: UserSchema = Depends(get_current_user)):
    return templates.TemplateResponse(
        "account.html", {"request": request, "current_user": user}
    )


@router.get("/api/account", response_model=UserSchema)
async def account_api(user: UserSchema = Depends(get_current_user)):
    return user


@router.post("/api/account/theme", response_model=BaseApiResponse)
async def update_theme(
    theme_update: ThemeUpdate, user: UserSchema = Depends(get_current_user)
):
    with db_session_manager() as db:
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
