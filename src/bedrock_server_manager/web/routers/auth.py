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

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse

from ...context import AppContext
from ..auth_utils import (
    authenticate_user,
    create_access_token,
    get_current_user,
)
from ..dependencies import get_app_context
from ..schemas import TokenResponse, UserLoginPayload, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# --- API Login Route ---
@router.post("/token", response_model=TokenResponse)
async def api_login_for_access_token(
    payload: UserLoginPayload,
    response: Response,
    app_context: AppContext = Depends(get_app_context),
):
    """
    Handles API user login and returns a JWT access token.
    """
    if not payload.username or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username and password cannot be empty.",
        )

    logger.info(f"API login attempt for '{payload.username}'")
    authenticated_username = authenticate_user(
        app_context, payload.username, payload.password
    )

    if not authenticated_username:
        logger.warning(f"Invalid API login attempt for '{payload.username}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    import datetime

    settings = app_context.settings
    if payload.remember_me:
        try:
            jwt_expires_weeks = float(settings.get("web.token_expires_weeks", 4.0))
        except (ValueError, TypeError):
            jwt_expires_weeks = 4.0
        access_token_expire_minutes = jwt_expires_weeks * 7 * 24 * 60
        expires_delta = datetime.timedelta(minutes=access_token_expire_minutes)
    else:
        expires_delta = datetime.timedelta(hours=24)

    access_token = create_access_token(
        data={"sub": authenticated_username},
        app_context=app_context,
        expires_delta=expires_delta,
    )

    logger.info(f"API login successful for '{payload.username}'. JWT created.")
    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        max_age=int(expires_delta.total_seconds()),
        samesite="lax",
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        message="Successfully authenticated.",
    )


# --- Logout Route ---
@router.get("/logout")
async def logout(
    response: Response,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Logs the current user out.
    Since we are using Bearer tokens, the client is responsible for discarding the token.
    This endpoint serves as an explicit logout action for auditing purposes.
    """
    username = current_user.username
    logger.info(f"User '{username}' explicitly logged out.")

    response.delete_cookie(key="access_token_cookie")
    return JSONResponse(
        content={"status": "success", "message": "Successfully logged out."},
        status_code=status.HTTP_200_OK,
    )
