"""FastAPI router for user authentication and session management."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from pydantic import SecretStr

from ...context import AppContext
from ..access_metadata import describe_access
from ..auth import (
    authenticate_user,
    create_access_token,
    token_lifetime,
)
from ..authorization import assigned_session, current_authorization
from ..cookies import clear_session_cookie, deliver_session, is_cookie_mode
from ..deps import get_app_context, get_current_user
from ..schemas import BaseApiResponse, TokenResponse, UserResponse
from ..schemas.auth import PasskeyLoginOptionsRequest, PasskeyLoginVerifyRequest
from ..schemas.security import PasskeyOptionsResponse
from ..trusted_devices import deliver_device, device_token

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
    remember_device: Annotated[bool, Form()] = False,
    trusted_device_token: Annotated[Optional[SecretStr], Form()] = None,
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
    proof = None
    cookie_mode = is_cookie_mode(request)
    if authenticated_username and owner is not None and owner.is_active:
        proof = await app_context.trusted_device_service.verify_factor(
            owner.access_id,
            owner.auth_revision,
            otp,
            device_token(
                request, owner.access_id, trusted_device_token, cookie_login=cookie_mode
            ),
        )
        if proof is None and not otp:
            raise HTTPException(
                401,
                "Authenticator or recovery code required",
                headers={"WWW-Authenticate": "Bearer", "X-BSM-MFA": "required"},
            )
    if proof is None:
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
    expires_delta = token_lifetime(settings, remember_me=remember_me)

    access_token = await create_access_token(
        data={"sub": authenticated_username, "authv": auth_revision},
        app_context=app_context,
        expires_delta=expires_delta,
        factor_proof=proof,
    )

    issued_device = (
        await app_context.trusted_device_service.remember(proof, request)
        if remember_device
        else None
    )

    await app_context.session_service.annotate(
        jwt.get_unverified_claims(access_token)["sid"], request
    )
    await app_context.session_service.authentication_succeeded(form_data.username)
    await app_context.session_service.publish(owner_id, "login")
    logger.info("User '%s' signed in.", form_data.username)
    token_value, cookie_mode = deliver_session(response, request, access_token)
    return TokenResponse(
        access_token=token_value,
        token_type="bearer",
        message="Successfully authenticated.",
        **deliver_device(
            response, request, owner_id, issued_device, cookie_mode=cookie_mode
        ),
    )


@router.post(
    "/passkey/options",
    operation_id="begin_passkey_login",
    response_model=PasskeyOptionsResponse,
)
@describe_access("public", authentication="none", additional_checks=[])
async def passkey_login_options(
    request: Request,
    payload: Optional[PasskeyLoginOptionsRequest] = None,
    app_context: AppContext = Depends(get_app_context),
) -> PasskeyOptionsResponse:
    """Issue a single-use WebAuthn authentication challenge for passkey sign-in."""
    username = payload.username if payload else None
    await app_context.session_service.throttle(
        username or "",
        request.client.host if request.client else "",
        "passkey_login",
    )
    options = await app_context.session_service.begin_passkey_authentication(
        request, username=username, purpose="login"
    )
    return PasskeyOptionsResponse(**options)


@router.post(
    "/passkey/verify",
    operation_id="complete_passkey_login",
    response_model=TokenResponse,
)
@describe_access("public", authentication="none", additional_checks=[])
async def passkey_login_verify(
    request: Request,
    response: Response,
    payload: PasskeyLoginVerifyRequest,
    app_context: AppContext = Depends(get_app_context),
) -> TokenResponse:
    """Verify a WebAuthn passkey assertion and establish an authenticated session."""
    username, proof = await app_context.session_service.complete_passkey_login(
        payload, request
    )
    expires_delta = token_lifetime(
        app_context.settings, remember_me=payload.remember_me
    )
    access_token = await create_access_token(
        data={"sub": username, "authv": proof.auth_revision},
        app_context=app_context,
        expires_delta=expires_delta,
        factor_proof=proof,
    )
    session_id = jwt.get_unverified_claims(access_token)["sid"]
    await app_context.session_service.annotate(session_id, request)
    logger.info("User '%s' signed in with passkey.", username)
    token_value, _ = deliver_session(response, request, access_token)
    return TokenResponse(
        access_token=token_value,
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
    expires_delta = token_lifetime(settings, remember_me=remember_me)

    access_token = await create_access_token(
        data={
            "sub": current_user.username,
            "sid": getattr(request.state, "session_id", None),
        },
        app_context=app_context,
        expires_delta=expires_delta,
    )

    logger.debug("Token refreshed for '%s'.", current_user.username)
    token_value, _ = deliver_session(
        response, request, access_token, allow_existing=True
    )
    return TokenResponse(
        access_token=token_value,
        token_type="bearer",
        message="Successfully refreshed token.",
    )


# --- Logout Route ---
@router.post("/logout", operation_id="logout", response_model=BaseApiResponse)
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
    authorization = current_authorization.get() or getattr(
        request.state, "authorization", None
    )
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
