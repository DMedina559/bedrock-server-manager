# bedrock_server_manager/web/routers/setup.py
"""
FastAPI router for the initial setup of the application.
"""
import logging
from fastapi import APIRouter, Request, Depends, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ...db.database import get_db
from ...db.models import User
from ..templating import templates
from ..auth_utils import pwd_context, get_current_user_optional
from ..schemas import User as UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/setup",
    tags=["Setup"],
)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def setup_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user_optional),
):
    """
    Serves the setup page if no users exist in the database.
    """
    if db.query(User).first():
        # If a user already exists, redirect to home page, as setup is complete
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request, "setup.html", {"request": request, "current_user": current_user}
    )


from pydantic import BaseModel


class CreateFirstUserRequest(BaseModel):
    username: str
    password: str


@router.post("", include_in_schema=False)
async def create_first_user(
    request: Request,
    data: CreateFirstUserRequest,
    db: Session = Depends(get_db),
):
    """
    Creates the first user (admin) in the database.
    """
    if db.query(User).first():
        # If a user already exists, prevent creating another first user
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Setup already completed. Users exist.",
            },
        )

    hashed_password = pwd_context.hash(data.password)
    user = User(username=data.username, hashed_password=hashed_password, role="admin")

    try:
        db.add(user)
        db.commit()
        db.refresh(user)  # Refresh the user object to get its ID if needed

        logger.info(f"First user '{data.username}' created with admin role.")

        # Return JSON response with redirect_url, consistent with register.py
        return JSONResponse(
            content={
                "status": "success",
                "message": "Admin account created successfully. Please log in.",
                "redirect_url": "/auth/login?message=Admin account created successfully. Please log in.",
            },
            status_code=status.HTTP_200_OK,
        )

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
