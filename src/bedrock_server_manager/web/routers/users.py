# bedrock_server_manager/web/routers/users.py
"""
FastAPI router for user management.
"""
import logging
from fastapi import APIRouter, Request, Depends, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import User
from ..templating import get_templates
from ..auth_utils import get_current_user, pwd_context
from ..schemas import User as UserSchema
from ..auth_utils import get_admin_user, get_moderator_user
from .audit_log import create_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def users_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_moderator_user),
):
    """
    Serves the user management page.
    """
    users = db.query(User).all()
    return get_templates().TemplateResponse(
        request,
        "users.html",
        {"request": request, "users": users, "current_user": current_user},
    )


from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str


class UpdateUserRoleRequest(BaseModel):
    role: str


@router.post("/create", include_in_schema=False)
async def create_user(
    request: Request,
    data: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_admin_user),
):
    """
    Creates a new user.
    """
    hashed_password = pwd_context.hash(data.password)
    user = User(username=data.username, hashed_password=hashed_password, role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)

    create_audit_log(
        db,
        current_user.id,
        "create_user",
        {"user_id": user.id, "username": user.username, "role": user.role},
    )

    logger.info(
        f"User '{data.username}' created with role '{data.role}' by '{current_user.username}'."
    )
    return {"status": "success"}


@router.post("/{user_id}/delete", include_in_schema=False)
async def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_admin_user),
):
    """
    Deletes a user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        create_audit_log(
            db,
            current_user.id,
            "delete_user",
            {"user_id": user.id, "username": user.username},
        )
        db.delete(user)
        db.commit()
        logger.info(f"User '{user.username}' deleted by '{current_user.username}'.")
        return {"status": "success"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User with id {user_id} not found.",
    )


@router.post("/{user_id}/disable", include_in_schema=False)
async def disable_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_admin_user),
):
    """
    Disables a user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        if user.role == "admin":
            active_admins = (
                db.query(User)
                .filter(User.role == "admin", User.is_active == True)
                .count()
            )
            if active_admins <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot disable the last active admin.",
                )

        user.is_active = False
        db.commit()
        create_audit_log(
            db,
            current_user.id,
            "disable_user",
            {"user_id": user.id, "username": user.username},
        )
        logger.info(f"User '{user.username}' disabled by '{current_user.username}'.")
        return {"status": "success"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User with id {user_id} not found.",
    )


@router.post("/{user_id}/enable", include_in_schema=False)
async def enable_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_admin_user),
):
    """
    Enables a user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_active = True
        db.commit()
        create_audit_log(
            db,
            current_user.id,
            "enable_user",
            {"user_id": user.id, "username": user.username},
        )
        logger.info(f"User '{user.username}' enabled by '{current_user.username}'.")
        return {"status": "success"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User with id {user_id} not found.",
    )


@router.post("/{user_id}/role", include_in_schema=False)
async def update_user_role(
    request: Request,
    user_id: int,
    data: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_admin_user),
):
    """
    Updates a user's role.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        if user.role == "admin" and data.role != "admin":
            active_admins = (
                db.query(User)
                .filter(User.role == "admin", User.is_active == True)
                .count()
            )
            if active_admins <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change the role of the last active admin.",
                )
        original_role = user.role
        user.role = data.role
        db.commit()
        create_audit_log(
            db,
            current_user.id,
            "update_user_role",
            {
                "user_id": user.id,
                "username": user.username,
                "original_role": original_role,
                "new_role": data.role,
            },
        )
        logger.info(
            f"User '{user.username}' role changed to '{data.role}' by '{current_user.username}'."
        )
        return {"status": "success"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User with id {user_id} not found.",
    )
