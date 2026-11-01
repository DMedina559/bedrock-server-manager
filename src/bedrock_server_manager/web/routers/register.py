"""
FastAPI router for user registration management.

This module provides endpoints for:
- Generating registration tokens (Admin only).
- Serving the registration page.
- Handling user registration submissions.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Security
from fastapi.responses import JSONResponse

from ...context import AppContext
from ..access_metadata import describe_access
from ..access_policy import Permission
from ..auth import get_password_hash_async
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import BaseApiResponse, GenerateTokenPayload, UserLoginPayload
from ..schemas import UserResponse as UserSchema
from ..schemas.base import RegistrationResponse

# bedrock_server_manager/web/routers/register.py


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/register", tags=["Registration"])


@router.post(
    "/generate-token",
    operation_id="generate_registration_token",
    response_model=RegistrationResponse,
)
async def generate_token(
    request: Request,
    data: GenerateTokenPayload,
    current_user: UserSchema = Security(
        require_permissions, scopes=[Permission.USERS_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> RegistrationResponse:
    """
    Generates a new registration token.
    """
    token = await app_context.user_service.create_registration_token(role=data.role)
    await app_context.session_service.event(
        current_user.id, "registration_token_created", role=data.role
    )

    base_url = str(request.base_url)
    registration_link = f"{base_url}app/register/{token}"

    logger.info(
        "Registration link created for role '%s' by user '%s'.",
        data.role,
        current_user.username,
    )

    return RegistrationResponse(
        status="success",
        message="Token generated successfully.",
        registration_url=registration_link,
    )


@router.get(
    "/validate/{token}",
    operation_id="validate_registration_token",
    response_model=BaseApiResponse,
)
@describe_access(
    "custom", authentication="none", additional_checks=["registration-token"]
)
async def validate_token(
    request: Request,
    token: Annotated[str, Path(max_length=128)],
    app_context: AppContext = Depends(get_app_context),
):
    """Check if a registration token is valid."""
    await app_context.session_service.throttle(
        username="",
        peer=request.client.host if request.client else "",
        operation="register",
    )
    if not await app_context.user_service.validate_registration_token(token):
        raise HTTPException(status_code=404, detail="Invalid or expired token.")

    return JSONResponse(content={"status": "success", "message": "Token is valid."})


@router.post(
    "/{token}",
    operation_id="register_user",
    response_model=BaseApiResponse,
)
@describe_access(
    "custom", authentication="none", additional_checks=["registration-token"]
)
async def register_user(
    request: Request,
    token: Annotated[str, Path(max_length=128)],
    data: UserLoginPayload,
    app_context: AppContext = Depends(get_app_context),
):
    """Create a new user from a registration token."""
    await app_context.session_service.throttle(
        username=data.username,
        peer=request.client.host if request.client else "",
        operation="register",
    )
    # Reject invalid/expired invitations through a cheap lookup before computing password hash
    if not await app_context.user_service.validate_registration_token(token):
        raise HTTPException(
            status_code=404, detail="Invalid or expired registration token."
        )

    # Hash the password outside long-lived database transactions
    hashed_password = await get_password_hash_async(data.password.get_secret_value())

    # Revalidate and consume the invitation atomically when creating the account
    record = await app_context.user_service.create_account(
        data.username,
        hashed_password,
        token=token,
    )
    if record is None:
        raise HTTPException(
            status_code=404, detail="Invalid or expired registration token."
        )
    await app_context.session_service.event(
        record.id, "account_registered", role=record.role
    )
    return JSONResponse(
        content={
            "status": "success",
            "message": "Registration successful. Please log in.",
        }
    )
