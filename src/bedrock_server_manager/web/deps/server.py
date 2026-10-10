import logging

from fastapi import Depends, HTTPException, Path, status

from ...context import AppContext
from ...error import InvalidServerNameError
from .context import get_app_context

logger = logging.getLogger(__name__)


async def validate_server_exists(
    server_name: str = Path(..., title="The name of the server", min_length=1),
    app_context: AppContext = Depends(get_app_context),
) -> str:
    """
    FastAPI dependency to validate if a server identified by `server_name` exists.

    This dependency calls :func:`~bedrock_server_manager.utils.server.validate_server`.
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
    logger.debug("Dependency: Validating existence of server '%s'.", server_name)
    from ...utils import server as server_utils

    try:
        server_utils.core_validate_server_name_format(server_name)

        if not await server_utils.validate_server(
            server_name=server_name, app_context=app_context
        ):
            logger.warning("Dependency: Server '%s' not found or invalid.", server_name)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' is not installed or the installation is invalid.",
            )
        # If server exists, the dependency does nothing and request proceeds.
        logger.debug("Dependency: Server '%s' validated successfully.", server_name)
        return server_name  # Can return the validated item if needed by the route

    except InvalidServerNameError as e:  # If server_name format is invalid
        logger.warning(
            "Dependency: Invalid server name format for '%s': %s", server_name, e
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
