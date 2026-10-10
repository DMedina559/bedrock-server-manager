# bedrock_server_manager/web/routers/auth.py
"""
FastAPI router for user authentication and session management.

This module defines endpoints related to user login and logout for the
Bedrock Server Manager web interface. It handles:

- Processing API login requests (typically form submissions) to authenticate users
  against environment variable credentials and issue JWT access tokens
  (:func:`~.api_login_for_access_token`). Tokens are set as HTTP-only cookies.
- Handling user logout by clearing the authentication cookie
  (:func:`~.logout`).

It uses utilities from :mod:`~bedrock_server_manager.web.auth_utils` for
password verification, token creation, and user retrieval from tokens.
Authentication is required for most parts of the application, and these routes
facilitate that access control.
"""

import datetime
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from ...context import AppContext
from ...utils import (
    authenticate_user,
    create_access_token,
)
from ..deps import get_app_context, get_current_user
from ..schemas import TokenResponse, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# --- API Login Route ---
@router.post(
    "/token", operation_id="login", response_model=TokenResponse, tags=["Login"]
)
async def api_login_for_access_token(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    remember_me: Annotated[bool, Form()] = False,
    app_context: AppContext = Depends(get_app_context),
) -> TokenResponse:
    """
    Handles API user login and returns a JWT access token.
    """
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
    is_secure = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "") == "https"
    )

    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        max_age=int(expires_delta.total_seconds()),
        samesite="lax",
        secure=is_secure,
        path="/",
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
    tags=["Login"],
)
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
        except Exception:
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
    is_secure = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "") == "https"
    )

    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        max_age=int(expires_delta.total_seconds()),
        samesite="lax",
        secure=is_secure,
        path="/",
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        message="Successfully refreshed token.",
    )


# --- Logout Route ---
@router.get("/logout", operation_id="logout")
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
    is_secure = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "") == "https"
    )

    response.delete_cookie(
        key="access_token_cookie",
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
    )
    return response
