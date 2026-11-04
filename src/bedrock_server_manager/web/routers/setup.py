"""
FastAPI router for the initial setup of the application.

This module provides endpoints for:
- Handling the creation of the first user (System Admin).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import jwt

from ...context import AppContext
from ..access_metadata import describe_access
from ..auth import (
    create_access_token,
    get_password_hash_async,
)
from ..cookies import deliver_session
from ..deps import get_app_context
from ..schemas import SetupStatusResponse, TokenResponse, UserLoginPayload

# bedrock_server_manager/web/routers/setup.py


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["Application Setup"])


@router.get(
    "/status",
    operation_id="get_setup_status",
    response_model=SetupStatusResponse,
)
@describe_access("public", authentication="none", additional_checks=[])
async def get_setup_status(
    app_context: AppContext = Depends(get_app_context),
) -> SetupStatusResponse:
    """Return whether the application needs initial setup."""
    return SetupStatusResponse(needs_setup=await app_context.check_setup())


@router.post(
    "/create-first-user",
    operation_id="create_first_user",
    response_model=TokenResponse,
)
@describe_access(
    "custom", authentication="none", additional_checks=["first-account-only"]
)
async def create_first_user(
    request: Request,
    response: Response,
    data: UserLoginPayload,
    app_context: AppContext = Depends(get_app_context),
) -> TokenResponse:
    """Create the first user (admin) in the database."""
    await app_context.session_service.throttle(
        username=data.username,
        peer=request.client.host if request.client else "",
        operation="setup",
    )
    if not await app_context.check_setup():
        # If an admin user already exists, prevent creating another first user
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application has already been set up.",
        )

    record = await app_context.user_service.create_account(
        data.username,
        await get_password_hash_async(data.password.get_secret_value()),
        first_admin=True,
    )
    if record is None:
        raise HTTPException(
            status_code=400, detail="Could not create the first account."
        )
    app_context._needs_setup = False
    access_token = await create_access_token(
        data={"sub": record.username}, app_context=app_context
    )
    await app_context.session_service.annotate(
        jwt.get_unverified_claims(access_token)["sid"], request
    )
    token_value, _ = deliver_session(response, request, access_token)
    return TokenResponse(
        message="Admin account created and logged in successfully.",
        access_token=token_value,
        token_type="bearer",
    )
