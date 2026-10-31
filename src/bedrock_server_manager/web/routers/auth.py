"""FastAPI router for user authentication and session management."""

import datetime
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt

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
    otp: Annotated[str, Form(max_length=128)] = "",
    app_context: AppContext = Depends(get_app_context),
) -> TokenResponse:
    """Handle API user login and return a JWT access token."""
    if not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username and password cannot be empty.",
        )

    await app_context.session_service.throttle(
        form_data.username, request.client.host if request.client else ""
    )
    logger.debug("API login attempt received")
    async with app_context.storage.transaction() as session:
        owner = await app_context.storage.user_repo.get_user_by_username(
            session, form_data.username
        )
        owner_id = owner.access_id if owner else None
        owner_user_id = owner.id if owner else None
        auth_revision = owner.auth_revision if owner else None
    authenticated_username = await authenticate_user(
        app_context, form_data.username, form_data.password
    )
    if authenticated_username and (
        owner is None
        or not owner.is_active
        or not await app_context.session_service.verify_factor(owner_id, otp)
    ):
        authenticated_username = None
    if not authenticated_username and owner_user_id:
        await app_context.session_service.event(owner_user_id, "login_failed")
    if not authenticated_username:
        logger.warning("Invalid API login attempt")
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
        data={"sub": authenticated_username, "authv": auth_revision},
        app_context=app_context,
        expires_delta=expires_delta,
    )

    await app_context.session_service.annotate(
        jwt.get_unverified_claims(access_token)["sid"], request
    )
    await app_context.session_service.authentication_succeeded(form_data.username)
    logger.info("User '%s' signed in.", form_data.username)
    cookie_mode = request.headers.get("x-bsm-auth-mode") == "cookie"
    if cookie_mode:
        request.state.issued_session_id = jwt.get_unverified_claims(access_token)["sid"]
        set_session_cookie(
            response,
            request,
            access_token,
            max_age=max(
                0,
                jwt.get_unverified_claims(access_token)["exp"]
                - int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            ),
        )
    return TokenResponse(
        access_token="" if cookie_mode else access_token,
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
        data={
            "sub": current_user.username,
            "sid": getattr(request.state, "session_id", None),
        },
        app_context=app_context,
        expires_delta=expires_delta,
    )

    logger.debug("Token refreshed for '%s'.", current_user.username)
    cookie_mode = request.headers.get("x-bsm-auth-mode") == "cookie" or (
        request.headers.get("x-bsm-auth-mode") is None
        and getattr(request.state, "credential_source", None) == "cookie"
    )
    if cookie_mode:
        request.state.issued_session_id = jwt.get_unverified_claims(access_token)["sid"]
        set_session_cookie(
            response,
            request,
            access_token,
            max_age=max(
                0,
                jwt.get_unverified_claims(access_token)["exp"]
                - int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            ),
        )
    return TokenResponse(
        access_token="" if cookie_mode else access_token,
        token_type="bearer",
        message="Successfully refreshed token.",
    )


# --- Logout Route ---
@router.post("/logout", operation_id="logout")
@router.get(
    "/logout", operation_id="logout_legacy", deprecated=True, include_in_schema=False
)
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
    authorization = getattr(request.state, "authorization", None)
    if authorization and authorization.session_id:
        await request.app.state.app_context.session_service.revoke(
            authorization.owner_id, identifier=authorization.session_id, reason="logout"
        )
    logger.info("User '%s' explicitly logged out.", username)

    response = JSONResponse(
        content={"status": "success", "message": "Successfully logged out."},
        status_code=status.HTTP_200_OK,
    )
    if getattr(request.state, "credential_source", None) == "cookie":
        clear_session_cookie(response, request)
    return response
