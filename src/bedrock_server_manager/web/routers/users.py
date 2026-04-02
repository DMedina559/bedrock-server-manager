# bedrock_server_manager/web/routers/users.py
"""
FastAPI router for user management.

This module provides endpoints for:
- Listing users (Moderator+).
- Creating users (Admin).
- Deleting users (Admin).
- Enabling/Disabling users (Admin).
- Updating user roles (Admin).
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ...context import AppContext
from ...db.models import User
from ..auth_utils import get_admin_user, get_moderator_user
from ..dependencies import get_app_context
from ..schemas import BaseApiResponse, UpdateUserRolePayload
from ..schemas import UserResponse as UserSchema
from .audit_log import create_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)


def _get_active_admin_count(db) -> int:
    """Helper function to get the count of active admins."""
    return int(
        db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
    )


@router.get("/list", response_model=List[UserSchema])
async def list_users_api(
    current_user: UserSchema = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the list of users as JSON.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        users = db.query(User).all()
        return users


@router.post("/{user_id}/delete", response_model=BaseApiResponse)
async def delete_user(
    user_id: int,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Deletes a user.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            # Prevent deleting the last admin
            if user.role == "admin" and _get_active_admin_count(db) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last active admin.",
                )

            create_audit_log(
                app_context,
                current_user.id,
                "delete_user",
                {"user_id": user.id, "username": user.username},
            )
            db.delete(user)
            db.commit()
            logger.info(
                f"UserResponse '{user.username}' deleted by '{current_user.username}'."
            )
            return BaseApiResponse(status="success")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"UserResponse with id {user_id} not found.",
    )


@router.post("/{user_id}/disable", response_model=BaseApiResponse)
async def disable_user(
    user_id: int,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Disables a user.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if user.role == "admin" and _get_active_admin_count(db) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot disable the last active admin.",
                )

            user.is_active = False
            db.commit()
            create_audit_log(
                app_context,
                current_user.id,
                "disable_user",
                {"user_id": user.id, "username": user.username},
            )
            logger.info(
                f"UserResponse '{user.username}' disabled by '{current_user.username}'."
            )
            return BaseApiResponse(status="success")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"UserResponse with id {user_id} not found.",
    )


@router.post("/{user_id}/enable", response_model=BaseApiResponse)
async def enable_user(
    user_id: int,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Enables a user.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = True
            db.commit()
            create_audit_log(
                app_context,
                current_user.id,
                "enable_user",
                {"user_id": user.id, "username": user.username},
            )
            logger.info(
                f"UserResponse '{user.username}' enabled by '{current_user.username}'."
            )
            return BaseApiResponse(status="success")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"UserResponse with id {user_id} not found.",
    )


@router.post("/{user_id}/role", response_model=BaseApiResponse)
async def update_user_role(
    user_id: int,
    data: UpdateUserRolePayload,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Updates a user's role.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if (
                user.role == "admin"
                and data.role != "admin"
                and _get_active_admin_count(db) <= 1
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change the role of the last active admin.",
                )
            original_role = user.role
            user.role = data.role
            db.commit()
            create_audit_log(
                app_context,
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
                f"UserResponse '{user.username}' role changed to '{data.role}' by '{current_user.username}'."
            )
            return BaseApiResponse(status="success")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"UserResponse with id {user_id} not found.",
    )
