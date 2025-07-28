# bedrock_server_manager/web/routers/setup.py
"""
FastAPI router for the initial setup of the application.
"""
import logging
from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import User
from ...web.templating import templates
from ...web.auth_utils import pwd_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/setup",
    tags=["Setup"],
)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def setup_page(request: Request, db: Session = Depends(get_db)):
    """
    Serves the setup page if no users exist in the database.
    """
    if db.query(User).first():
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "setup.html", {"request": request})


@router.post("", include_in_schema=False)
async def create_first_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Creates the first user in the database.
    """
    if db.query(User).first():
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    hashed_password = pwd_context.hash(password)
    user = User(username=username, hashed_password=hashed_password, role="admin")
    db.add(user)
    db.commit()

    logger.info(f"First user '{username}' created with admin role.")
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
