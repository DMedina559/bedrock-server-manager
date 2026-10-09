# bedrock_server_manager/web/routers/setup.py
"""
FastAPI router for the initial setup of the application.

This module provides endpoints for:
- Handling the creation of the first user (System Admin).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ...context import AppContext
from ...utils import (
    create_access_token,
    get_password_hash,
)
from ..deps import get_app_context
from ..schemas import SetupStatusResponse, UserLoginPayload

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/setup", tags=["Application Setup"], include_in_schema=False
)


@router.get(
    "/status",
    operation_id="get_setup_status",
    response_model=SetupStatusResponse,
)
async def get_setup_status(
    app_context: AppContext = Depends(get_app_context),
) -> SetupStatusResponse:
    """
    Returns whether the application needs initial setup.
    """
    return SetupStatusResponse(needs_setup=app_context.needs_setup)


@router.post(
    "/create-first-user",
    operation_id="create_first_user",
)
async def create_first_user(
    data: UserLoginPayload,
    app_context: AppContext = Depends(get_app_context),
):
    """
    Creates the first user (admin) in the database.
    """
    if not app_context.needs_setup:
        # If an admin user already exists, prevent creating another first user
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application has already been set up.",
        )

    record = await app_context.user_service.create_account(
        data.username, get_password_hash(data.password), first_admin=True
    )
    if record is None:
        raise HTTPException(
            status_code=400, detail="Could not create the first account."
        )
    app_context._needs_setup = False
    access_token = await create_access_token(
        data={"sub": record.username}, app_context=app_context
    )
    response = JSONResponse(
        content={
            "status": "success",
            "message": "Admin account created and logged in successfully.",
            "access_token": access_token,
            "token_type": "bearer",
        }
    )
    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response
