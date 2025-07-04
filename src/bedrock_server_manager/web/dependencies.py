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
from fastapi import HTTPException, status, Path, Request

from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.error import (
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)


async def validate_server_exists(
    server_name: str = Path(..., title="The name of the server", min_length=1)
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
        validation_result = utils_api.validate_server_exist(server_name)
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
