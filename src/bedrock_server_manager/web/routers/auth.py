"""FastAPI router for user authentication and session management."""

import datetime
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from ...context import AppContext
from ..access_metadata import describe_access
from ..auth import (
    authenticate_user,
    create_access_token,
)
from ..authorization import assigned_session
from ..cookies import clear_session_cookie, set_session_cookie
from ..deps import get_app_context, get_current_user
from ..schemas import TokenResponse, UserResponse

# bedrock_server_manager/web/routers/auth.py


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- API Login Route ---
@router.post(
    "/token",
    operation_id="login",
    response_model=TokenResponse,
)
@describe_access("public", authentication="none", additional_checks=[])
async def api_login_for_access_token(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    remember_me: Annotated[bool, Form()] = False,
    app_context: AppContext = Depends(get_app_context),
) -> TokenResponse:
    """Handle API user login and return a JWT access token."""
    if not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username and password cannot be empty.",
        )

    logger.debug("API login attempt for '%s'", form_data.username)
    authenticated_username = await authenticate_user(
        app_context, form_data.username, form_data.password
    )

    if not authenticated_username:
        logger.warning("Invalid API login attempt for '%s'.", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    settings = app_context.settings
    if remember_me:
        try:
            jwt_expires_weeks = float(settings.get("web.token_expires_weeks", 4.0))
        except (ValueError, TypeError):
            jwt_expires_weeks = 4.0
        access_token_expire_minutes = jwt_expires_weeks * 7 * 24 * 60
        expires_delta = datetime.timedelta(minutes=access_token_expire_minutes)
    else:
        expires_delta = datetime.timedelta(hours=24)

    access_token = await create_access_token(
        data={"sub": authenticated_username},
        app_context=app_context,
        expires_delta=expires_delta,
    )

    logger.info("User '%s' signed in.", form_data.username)
    set_session_cookie(
        response,
        request,
        access_token,
        max_age=int(expires_delta.total_seconds()),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        message="Successfully authenticated.",
    )


@router.post(
    "/reauth",
    operation_id="reauthenticate",
    response_model=TokenResponse,
)
@assigned_session
async def reauth(
    request: Request,
    response: Response,
    remember_me: Optional[bool] = None,
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> TokenResponse:
    """
    Refreshes the JWT access token for an already authenticated user.
    Supports form data, JSON body, or query parameters.
    """
    if remember_me is None:
        # Check if remember_me was provided in form data or json body
        try:
            content_type = request.headers.get("content-type", "").lower()
            if "application/json" in content_type:
                json_data = await request.json()
                if isinstance(json_data, dict):
                    remember_me = bool(json_data.get("remember_me", False))
            elif (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                form_data = await request.form()
                val = form_data.get("remember_me")
                if val is not None:
                    remember_me = str(val).lower() in ("true", "1", "yes", "on")
        except ValueError:
            # Optional remember-me data may be absent or malformed.
            pass

    if remember_me is None:
        remember_me = False

    settings = app_context.settings
    if remember_me:
        try:
            jwt_expires_weeks = float(settings.get("web.token_expires_weeks", 4.0))
        except (ValueError, TypeError):
            jwt_expires_weeks = 4.0
        access_token_expire_minutes = jwt_expires_weeks * 7 * 24 * 60
        expires_delta = datetime.timedelta(minutes=access_token_expire_minutes)
    else:
        expires_delta = datetime.timedelta(hours=24)

    access_token = await create_access_token(
        data={"sub": current_user.username},
        app_context=app_context,
        expires_delta=expires_delta,
    )

    logger.debug("Token refreshed for '%s'.", current_user.username)
    set_session_cookie(
        response,
        request,
        access_token,
        max_age=int(expires_delta.total_seconds()),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        message="Successfully refreshed token.",
    )


# --- Logout Route ---
@router.get("/logout", operation_id="logout")
@assigned_session
async def logout(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Logs the current user out.
    Since we are using Bearer tokens, the client is responsible for discarding the token.
    This endpoint serves as an explicit logout action for auditing purposes.
    """
    username = current_user.username
    logger.info("User '%s' explicitly logged out.", username)

    response = JSONResponse(
        content={"status": "success", "message": "Successfully logged out."},
        status_code=status.HTTP_200_OK,
    )
    clear_session_cookie(response, request)
    return response
