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
from jose import jwt

from bedrock_server_manager.web.templating import templates
from bedrock_server_manager.web.auth_utils import (
    create_access_token,
    authenticate_user,
    get_current_user_optional,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from bedrock_server_manager.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


# --- Pydantic Models for Request/Response ---
class Token(BaseModel):
    access_token: str
    token_type: str
    message: Optional[str] = None


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    status: str
    message: str


# --- Web UI Login Page Route ---
@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """Serves the login page."""
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse("login.html", {"request": request, "form": {}})


# --- API Login Route ---
@router.post("/token", response_model=Token)
async def api_login_for_access_token(
    response: FastAPIResponse, username: str = Form(...), password: str = Form(...)
):
    """
    Handles API user login, creates JWT, and sets it as a cookie.
    This route is typically called by a form submission from the /login page or an API client.
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

    cookie_secure = settings.get("web.jwt_cookie_secure", False)
    cookie_samesite = settings.get("web.jwt_cookie_samesite", "Lax")

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
        "message": "Login successful! Redirecting...",
    }


# --- Logout Route ---
@router.get("/logout", response_model=MessageResponse)
async def logout(
    response: FastAPIResponse,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Logs the user out by clearing the JWT cookie.
    """
    username = current_user.get("username", "Unknown user")
    logger.info(f"User '{username}' logging out. Clearing JWT cookie.")

    response.delete_cookie(key="access_token_cookie", path="/")

    redirect_response = RedirectResponse(
        url="/auth/login", status_code=status.HTTP_302_FOUND
    )
    redirect_response.delete_cookie(key="access_token_cookie", path="/")
    redirect_url_with_message = (
        f"/auth/login?message=You%20have%20been%20successfully%20logged%20out."
    )
    final_response = RedirectResponse(
        url=redirect_url_with_message, status_code=status.HTTP_302_FOUND
    )
    final_response.delete_cookie(key="access_token_cookie", path="/")

    return final_response
