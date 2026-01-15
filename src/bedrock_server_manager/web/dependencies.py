# bedrock_server_manager/web/dependencies.py
"""Defines FastAPI dependencies for use in web route handlers.

Dependencies in FastAPI are a way to share logic, enforce constraints, or
provide resources to path operation functions. This module centralizes
common dependencies used across various API routes, such as validating
the existence of a server instance.

See Also:
    FastAPI Dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/
"""
import logging

from fastapi import HTTPException, Path, Request, status
from sqlalchemy.orm import Session

from ..api import utils as utils_api
from ..context import AppContext
from ..db.models import User
from ..error import InvalidServerNameError

logger = logging.getLogger(__name__)


def get_app_context(request: Request) -> "AppContext":
    """
    FastAPI dependency to get the application context from the request state.
    """
    return request.app.state.app_context


from fastapi import Depends
from fastapi.templating import Jinja2Templates


def get_templates(
    app_context: AppContext = Depends(get_app_context),
) -> "Jinja2Templates":
    """
    FastAPI dependency to get the Jinja2Templates instance from the application context.
    """
    return app_context.templates


async def validate_server_exists(
    server_name: str = Path(..., title="The name of the server", min_length=1),
    app_context: AppContext = Depends(get_app_context),
) -> str:
    """
    FastAPI dependency to validate if a server identified by `server_name` exists.

    This dependency calls :func:`~bedrock_server_manager.api.utils.validate_server_exist`.
    If the server does not exist or its name format is invalid, it raises an
    :class:`~fastapi.HTTPException` (status 404 or 400 respectively).
    Otherwise, it allows the request to proceed.

    Args:
        server_name (str): The name of the server, typically extracted from the
            URL path by FastAPI using :func:`~fastapi.Path`.

    Returns:
        str: The validated server name if found and valid.

    Raises:
        fastapi.HTTPException: With status code 404 if the server is not found
            or the installation is invalid.
        fastapi.HTTPException: With status code 400 if the `server_name`
            has an invalid format.
    """
    logger.debug(f"Dependency: Validating existence of server '{server_name}'.")
    try:
        name_validation_result = utils_api.validate_server_name_format(server_name)
        if name_validation_result.get("status") != "success":
            raise InvalidServerNameError(name_validation_result.get("message"))

        validation_result = utils_api.validate_server_exist(
            server_name=server_name, app_context=app_context
        )
        if validation_result.get("status") != "success":
            logger.warning(
                f"Dependency: Server '{server_name}' not found or invalid. Message: {validation_result.get('message')}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=validation_result.get(
                    "message", f"Server '{server_name}' not found or is invalid."
                ),
            )
        # If server exists, the dependency does nothing and request proceeds.
        logger.debug(f"Dependency: Server '{server_name}' validated successfully.")
        return server_name  # Can return the validated item if needed by the route

    except InvalidServerNameError as e:  # If server_name format is invalid
        logger.warning(
            f"Dependency: Invalid server name format for '{server_name}': {e}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
