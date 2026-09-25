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
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.future import select

from ...context import AppContext
from ...db.models import User
from ..deps import get_admin_user, get_app_context, get_moderator_user
from ..schemas import BaseApiResponse, UpdateUserRolePayload
from ..schemas import UserResponse as UserSchema
from .audit_log import create_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users",
    tags=["User Management"],
)


async def _get_active_admin_count(session) -> int:
    """Helper function to get the count of active admins."""
    result = await session.execute(
        select(func.count())
        .select_from(User)
        .filter(User.role == "admin", User.is_active.is_(True))
    )
    return int(result.scalar() or 0)


@router.get("/list", response_model=List[UserSchema])
async def list_users_api(
    current_user: UserSchema = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the list of users as JSON.
    """
    async with app_context.storage.transaction() as session:
        users = await app_context.storage.user_repo.get_all_users(session)
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
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.get_user_by_id(session, user_id)
        if user:
            if user.role == "admin" and await _get_active_admin_count(session) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last active admin.",
                )

            await create_audit_log(
                app_context,
                current_user.id,
                "delete_user",
                {"user_id": user.id, "username": str(user.username)},
            )
            await app_context.storage.user_repo.delete_user(session, user)
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
    async with app_context.storage.transaction() as session:
        user: Any = await app_context.storage.user_repo.get_user_by_id(session, user_id)
        if user:
            if user.role == "admin" and await _get_active_admin_count(session) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot disable the last active admin.",
                )

            user.is_active = False
            await create_audit_log(
                app_context,
                current_user.id,
                "disable_user",
                {"user_id": user.id, "username": str(user.username)},
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
    async with app_context.storage.transaction() as session:
        user: Any = await app_context.storage.user_repo.get_user_by_id(session, user_id)
        if user:
            user.is_active = True
            await create_audit_log(
                app_context,
                current_user.id,
                "enable_user",
                {"user_id": user.id, "username": str(user.username)},
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
    async with app_context.storage.transaction() as session:
        user: Any = await app_context.storage.user_repo.get_user_by_id(session, user_id)
        if user:
            if (
                user.role == "admin"
                and data.role != "admin"
                and await _get_active_admin_count(session) <= 1
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change the role of the last active admin.",
                )
            original_role = str(user.role)
            user.role = data.role
            await create_audit_log(
                app_context,
                current_user.id,
                "update_user_role",
                {
                    "user_id": user.id,
                    "username": str(user.username),
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
