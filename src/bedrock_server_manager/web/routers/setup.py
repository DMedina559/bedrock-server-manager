# bedrock_server_manager/web/routers/setup.py
"""
FastAPI router for the initial setup of the application.
"""
import logging
from fastapi import APIRouter, Request, Depends, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi.templating import Jinja2Templates

from ...db.models import User
from ..dependencies import get_templates, get_app_context
from ..auth_utils import (
    get_current_user_optional,
    create_access_token,
    get_password_hash,
)
from ..schemas import User as UserSchema
from ...context import AppContext

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/setup",
    tags=["Setup"],
)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def setup_page(
    request: Request,
    current_user: UserSchema = Depends(get_current_user_optional),
    app_context: AppContext = Depends(get_app_context),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the setup page if no users exist in the database.
    """
    with app_context.db.session_manager() as db:
        if db.query(User).first():
            # If a user already exists, redirect to home page, as setup is complete
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request, "setup.html", {"current_user": current_user}
    )


from pydantic import BaseModel


class CreateFirstUserRequest(BaseModel):
    username: str
    password: str


@router.post("/create-first-user", include_in_schema=False)
async def create_first_user(
    data: CreateFirstUserRequest,
    app_context: AppContext = Depends(get_app_context),
):
    """
    Creates the first user (admin) in the database.
    """
    with app_context.db.session_manager() as db:
        if db.query(User).first():
            # If a user already exists, prevent creating another first user
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Setup already completed. Users exist.",
                },
            )

        hashed_password = get_password_hash(data.password)
        user = User(
            username=data.username, hashed_password=hashed_password, role="admin"
        )

        try:
            db.add(user)
            db.commit()
            db.refresh(user)  # Refresh the user object to get its ID if needed

            logger.info(f"First user '{data.username}' created with admin role.")

            # Log the user in by creating an access token and setting it as a cookie
            access_token = create_access_token(
                data={"sub": user.username}, app_context=app_context
            )
            settings = app_context.settings
            cookie_secure = settings.get("web.jwt_cookie_secure", False)
            cookie_samesite = settings.get("web.jwt_cookie_samesite", "Lax")

            # Create the JSON response
            response = JSONResponse(
                content={
                    "status": "success",
                    "message": "Admin account created and logged in successfully.",
                    "redirect_url": "/settings?in_setup=true",
                },
                status_code=status.HTTP_200_OK,
            )

            # Set the cookie on the response
            response.set_cookie(
                key="access_token_cookie",
                value=access_token,
                httponly=True,
                secure=cookie_secure,
                samesite=cookie_samesite,
                path="/",
            )

            return response

        except IntegrityError:
            db.rollback()  # Rollback the transaction on database error
            logger.warning(
                f"Setup failed: Username '{data.username}' already exists (should not happen for first user)."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Username already exists. Please choose a different one.",
                },
            )
        except Exception as e:
            db.rollback()  # Rollback for any other unexpected errors
            logger.error(
                f"An unexpected error occurred during first user creation: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "status": "error",
                    "message": "An unexpected server error occurred during setup.",
                },
            )
