# bedrock_server_manager/web/routers/auth.py
"""
FastAPI router for user authentication and session management.

This module defines endpoints related to user login and logout for the
Bedrock Server Manager web interface. It handles:

- Displaying the HTML login page (:func:`~.login_page`).
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
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi import Response as FastAPIResponse
from fastapi import status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ...context import AppContext
from ..auth_utils import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_current_user_optional,
)
from ..dependencies import get_app_context, get_templates
from ..schemas import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# --- Pydantic Models for Request/Response ---
class Token(BaseModel):
    """Response model for successful authentication, providing an access token."""

    access_token: str
    token_type: str
    message: Optional[str] = None


class UserLogin(BaseModel):
    """Request model for user login credentials."""

    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1)


# --- Web UI Login Page Route ---
@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
    templates: Jinja2Templates = Depends(get_templates),
):
    """Serves the HTML login page."""
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        "login.html", {"request": request, "form": {}, "current_user": user}
    )


# --- API Login Route ---
@router.post("/token", response_model=Token)
async def api_login_for_access_token(
    response: FastAPIResponse,
    form_data: OAuth2PasswordRequestForm = Depends(),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Handles API user login, creates a JWT, and sets it as an HTTP-only cookie.
    """
    if not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Username and password cannot be empty.",
        )

    logger.info(f"API login attempt for '{form_data.username}'")
    authenticated_username = authenticate_user(
        app_context, form_data.username, form_data.password
    )

    if not authenticated_username:
        logger.warning(f"Invalid API login attempt for '{form_data.username}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": authenticated_username}, app_context=app_context
    )
    settings = app_context.settings
    cookie_secure = settings.get("web.jwt_cookie_secure", False)
    cookie_samesite = settings.get("web.jwt_cookie_samesite", "Lax")

    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        path="/",
    )
    logger.info(
        f"API login successful for '{form_data.username}'. JWT created and cookie set."
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Successfully authenticated.",
    }


@router.get("/refresh-token", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Refreshes the JWT access token for an authenticated user.

    This endpoint allows a client authenticated via a session cookie to request
    a new JWT access token. This is useful if the client has lost its stored
    token (e.g., cleared localStorage) but still has a valid session.
    """
    access_token = create_access_token(
        data={"sub": current_user.username}, app_context=app_context
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Token refreshed successfully.",
    }


# --- Logout Route ---
@router.get("/logout")
async def logout(
    response: FastAPIResponse,
    current_user: User = Depends(get_current_user),
):
    """
    Logs the current user out by clearing the JWT authentication cookie.
    """
    username = current_user.username
    logger.info(f"User '{username}' logging out. Clearing JWT cookie.")

    # Create the redirect response first, then operate on it for cookie deletion
    redirect_url_with_message = (
        f"/auth/login?message=You%20have%20been%20successfully%20logged%20out."
    )
    final_response = RedirectResponse(
        url=redirect_url_with_message, status_code=status.HTTP_302_FOUND
    )
    # Clear the cookie on the response that will actually be sent to the client
    final_response.delete_cookie(key="access_token_cookie", path="/")

    return final_response
