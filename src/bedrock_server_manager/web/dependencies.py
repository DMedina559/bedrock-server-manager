# bedrock_server_manager/web/dependencies.py
import logging
from fastapi import HTTPException, status, Path, Request

from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.error import (
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)


async def validate_server_exists(
    server_name: str = Path(..., title="The name of the server", min_length=1)
):
    """
    FastAPI dependency to validate if a server identified by `server_name` exists.
    Raises HTTPException(404) if the server does not exist or the name is invalid.
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
