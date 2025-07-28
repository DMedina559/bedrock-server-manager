# bedrock_server_manager/web/routers/users.py
"""
FastAPI router for user management.
"""
import logging
from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import User
from ..templating import templates
from ..auth_utils import get_current_user, pwd_context
from ..schemas import User as UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def users_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Serves the user management page.
    """
    users = db.query(User).all()
    return templates.TemplateResponse(
        request,
        "users.html",
        {"request": request, "users": users, "current_user": current_user},
    )


@router.post("/create", include_in_schema=False)
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Creates a new user.
    """
    if current_user.role != "admin":
        return RedirectResponse(url="/users", status_code=status.HTTP_403_FORBIDDEN)

    hashed_password = pwd_context.hash(password)
    user = User(username=username, hashed_password=hashed_password, role=role)
    db.add(user)
    db.commit()

    logger.info(
        f"User '{username}' created with role '{role}' by '{current_user.username}'."
    )
    return RedirectResponse(url="/users", status_code=status.HTTP_302_FOUND)


@router.post("/{user_id}/delete", include_in_schema=False)
async def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Deletes a user.
    """
    if current_user.role != "admin":
        return RedirectResponse(url="/users", status_code=status.HTTP_403_FORBIDDEN)

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
        logger.info(f"User '{user.username}' deleted by '{current_user.username}'.")

    return RedirectResponse(url="/users", status_code=status.HTTP_302_FOUND)
