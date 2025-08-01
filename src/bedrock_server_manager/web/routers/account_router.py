import os
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from bedrock_server_manager.web.auth_utils import get_current_user
from bedrock_server_manager.db.models import User
from bedrock_server_manager.db.database import db_session_manager
from ..templating import templates

router = APIRouter()


@router.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, user: User = Depends(get_current_user)):
    theme_dir = "themes"
    themes = [
        f.name for f in os.scandir(theme_dir) if f.is_file() and f.name.endswith(".css")
    ]
    return templates.TemplateResponse(
        "account.html", {"request": request, "user": user, "themes": themes}
    )
