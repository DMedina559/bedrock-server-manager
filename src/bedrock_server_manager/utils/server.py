# bedrock_server_manager/utils/server.py
"""Server naming, discovery and persistent player-directory helpers."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from ..contracts import ResourceFailure
from ..error import (
    AppFileNotFoundError,
    ConfigurationError,
    FileOperationError,
    InvalidServerNameError,
    MissingArgumentError,
    ResourceNotFoundError,
)
from ..failures import classify_failure
from ..logging import log_operation_error
from .threads import run_in_thread

if TYPE_CHECKING:
    from ..context import AppContext
    from ..state.app_state import AppState

logger = logging.getLogger(__name__)

# --- Server Stuff ---


def valid_server_names(state: "AppState") -> list[str]:
    """Shared file checks for server references; no process sampling."""
    base = state.settings.paths.servers
    executable = (
        "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
    )
    return sorted(
        name
        for name in state.servers.servers
        if re.fullmatch(r"[a-zA-Z0-9_-]+", name)
        and os.path.isfile(os.path.join(base, name, executable))
        and os.path.isfile(os.path.join(base, name, "server.properties"))
    )


def core_validate_server_name_format(server_name: str) -> None:
    """Validate the server identifier or raise ``InvalidServerNameError``."""
    if not isinstance(server_name, str) or not server_name:
        raise InvalidServerNameError("Server name must be a non-empty string.")
    if not re.fullmatch(r"^[a-zA-Z0-9_-]+$", server_name):
        raise InvalidServerNameError(
            "Invalid server name format. Only use letters (a-z, A-Z), "
            "numbers (0-9), hyphens (-), and underscores (_)."
        )
    logger.debug("Server name '%s' format is valid.", server_name)


# --- Server Discovery and Validation ---


async def validate_server(server_name: str, app_context: AppContext) -> bool:
    """Validates if a given server name corresponds to a valid installation."""
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for validation.")

    logger.debug("Validating server '%s' using BedrockServer class.", server_name)
    try:
        server_instance = app_context.get_server(server_name)
        is_valid = await server_instance.is_installed()
        if is_valid:
            logger.debug("Server '%s' validation successful.", server_name)
        else:
            logger.debug(
                "Server '%s' validation failed (directory or executable missing).",
                server_name,
            )
        return is_valid
    except (InvalidServerNameError, ResourceNotFoundError, AppFileNotFoundError):
        return False


async def get_servers_data(
    app_context: AppContext,
) -> Tuple[List[Dict[str, Any]], List[ResourceFailure]]:
    """Discovers and retrieves status data for all valid server instances."""
    servers_data: List[Dict[str, Any]] = []
    error_messages: List[ResourceFailure] = []

    base_dir = app_context.settings.get("paths.servers")

    def discover():
        if not base_dir or not os.path.isdir(base_dir):
            raise AppFileNotFoundError(str(base_dir), "Server base directory")
        with os.scandir(base_dir) as entries:
            return [entry.name for entry in entries if entry.is_dir()]

    candidates = await run_in_thread(discover)

    semaphore = asyncio.Semaphore(16)

    async def _inspect_candidate(server_name_candidate: str) -> None:
        async with semaphore:
            try:
                server = app_context.prepare_server(server_name_candidate)

                if not await server.is_installed():
                    logger.debug(
                        "Skipping '%s': Not a valid server installation.",
                        server_name_candidate,
                    )
                    return

                servers_data.append(
                    (await server.get_summary_info()).model_dump(mode="json")
                )

            except (
                FileOperationError,
                ConfigurationError,
                InvalidServerNameError,
            ) as e:
                msg = f"Could not get info for server '{server_name_candidate}': {e}"
                logger.warning(msg)
                error_messages.append(
                    ResourceFailure(
                        resource=server_name_candidate, error=classify_failure(e).error
                    )
                )
            except Exception as e:
                msg = f"An unexpected error occurred while processing server '{server_name_candidate}': {e}"
                log_operation_error(logger, msg, error=e)
                error_messages.append(
                    ResourceFailure(
                        resource=server_name_candidate, error=classify_failure(e).error
                    )
                )

    await asyncio.gather(*(_inspect_candidate(name) for name in candidates))

    servers_data.sort(key=lambda s: s.get("name", "").lower())
    return servers_data, error_messages
