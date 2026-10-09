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

from fastapi import APIRouter, Depends, HTTPException

from ...context import AppContext
from ..deps import get_admin_user, get_app_context, get_moderator_user
from ..schemas import BaseApiResponse, UpdateUserRolePayload
from ..schemas import UserResponse as UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users",
    tags=["User Management"],
)


@router.get("/list", operation_id="list_users", response_model=List[UserSchema])
async def list_users_api(
    current_user: UserSchema = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> List[UserSchema]:
    """
    Retrieves the list of users as JSON.
    """
    async with app_context.storage.transaction() as session:
        users = await app_context.storage.user_repo.get_all_users(session)
        return [UserSchema.model_validate(user, from_attributes=True) for user in users]


@router.post(
    "/{user_id}/delete", operation_id="delete_user", response_model=BaseApiResponse
)
async def delete_user(
    user_id: int,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    """
    Deletes a user.
    """
    result = await app_context.user_service.update_account(
        action="delete", user_id=user_id, actor_id=current_user.id
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"User with id {user_id} not found."
        )
    return BaseApiResponse(status="success")


@router.post(
    "/{user_id}/disable", operation_id="disable_user", response_model=BaseApiResponse
)
async def disable_user(
    user_id: int,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    result = await app_context.user_service.update_account(
        action="disable", user_id=user_id, actor_id=current_user.id
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"User with id {user_id} not found."
        )
    return BaseApiResponse(status="success")


@router.post(
    "/{user_id}/enable", operation_id="enable_user", response_model=BaseApiResponse
)
async def enable_user(
    user_id: int,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    result = await app_context.user_service.update_account(
        action="enable", user_id=user_id, actor_id=current_user.id
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"User with id {user_id} not found."
        )
    return BaseApiResponse(status="success")


@router.post(
    "/{user_id}/role", operation_id="update_user_role", response_model=BaseApiResponse
)
async def update_user_role(
    user_id: int,
    data: UpdateUserRolePayload,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    result = await app_context.user_service.update_account(
        action="role",
        user_id=user_id,
        values={"role": data.role},
        actor_id=current_user.id,
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"User with id {user_id} not found."
        )
    return BaseApiResponse(status="success")
