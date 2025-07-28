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
from typing import Optional, Dict, Any

from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException,
    Form,
    status,
    Response as FastAPIResponse,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from ..templating import templates
from ..auth_utils import (
    create_access_token,
    authenticate_user,
    get_current_user_optional,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from ..schemas import User
from ...instances import get_settings_instance

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
):
    """Serves the HTML login page.

    If a user is already authenticated (determined by the
    :func:`~.auth_utils.get_current_user_optional` dependency),
    they are redirected to the main application page ("/").
    Otherwise, it renders and returns the ``login.html`` template.

    Args:
        request (Request): The FastAPI request object.
        user (Optional[User]): The authenticated user object, if any.
                                         Injected by `get_current_user_optional`.

    Returns:
        HTMLResponse: Renders the ``login.html`` template if the user is not authenticated.
        RedirectResponse: Redirects to "/" if the user is already authenticated.
    """
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request, "login.html", {"request": request, "form": {}, "current_user": user}
    )


# --- API Login Route ---
@router.post("/token", response_model=Token)
async def api_login_for_access_token(
    response: FastAPIResponse, username: str = Form(...), password: str = Form(...)
):
    """
    Handles API user login, creates a JWT, and sets it as an HTTP-only cookie.

    This endpoint is typically called by a form submission from the ``/auth/login``
    page or by an API client seeking an access token. It authenticates credentials
    using :func:`~.auth_utils.authenticate_user` and, if successful, creates
    an access token using :func:`~.auth_utils.create_access_token`.
    The token is then set as an ``access_token_cookie``.

    Args:
        response (:class:`fastapi.FastAPIResponse`): FastAPI response object, used to set cookies.
        username (str): Username submitted via form data.
        password (str): Password submitted via form data.

    Returns:
        Token: A :class:`.Token` object containing the access token, token type,
               and a success message. The token is also set as an HTTP-only cookie.

    Raises:
        fastapi.HTTPException: With status code 401 if authentication fails.

    Example Response:
    .. code-block:: json

        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "message": "Successfully authenticated."
        }
    """
    logger.info(f"API login attempt for '{username}'")
    authenticated_username = authenticate_user(username, password)

    if not authenticated_username:
        logger.warning(f"Invalid API login attempt for '{username}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": authenticated_username})

    cookie_secure = get_settings_instance().get("web.jwt_cookie_secure", False)
    cookie_samesite = get_settings_instance().get("web.jwt_cookie_samesite", "Lax")

    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        max_age=int(ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        path="/",
    )
    logger.info(f"API login successful for '{username}'. JWT created and cookie set.")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Successfully authenticated.",
    }


# --- Logout Route ---
@router.get("/logout")
async def logout(
    response: FastAPIResponse,
    current_user: User = Depends(get_current_user),
):
    """
    Logs the current user out by clearing the JWT authentication cookie.

    This endpoint requires an authenticated user (verified by the
    :func:`~.auth_utils.get_current_user` dependency). It clears the
    ``access_token_cookie`` and then redirects the user to the login page
    with a logout success message.

    Args:
        response (:class:`fastapi.FastAPIResponse`): FastAPI response object. While available,
            cookie deletion is performed on the new `RedirectResponse` object.
        current_user (User): The authenticated user object, injected by dependency.
            Ensures only authenticated users can logout.

    Returns:
        :class:`fastapi.responses.RedirectResponse`: Redirects to the login page
            (``/auth/login``) with a success message in the query parameters.
            The ``access_token_cookie`` is cleared.
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
