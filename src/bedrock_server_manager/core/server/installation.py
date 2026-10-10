"""Bedrock installation component."""

import logging
from typing import TYPE_CHECKING

import aiofiles
import aiofiles.os
import aiofiles.ospath

from ...error import AppFileNotFoundError

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerInstallation:
    """Installation operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__), {"server_name": server.server_name}
        )

    async def validate_installation(self) -> bool:
        """Validates that the server installation directory and executable exist asynchronously."""
        self.logger.debug(
            "Validating installation for server '%s' in directory: %s",
            self.server.server_name,
            self.server.paths.server_dir,
        )
        if not await aiofiles.ospath.isdir(self.server.paths.server_dir):
            raise AppFileNotFoundError(self.server.paths.server_dir, "Server directory")
        if not await aiofiles.ospath.isfile(self.server.paths.bedrock_executable_path):
            raise AppFileNotFoundError(
                self.server.paths.bedrock_executable_path, "Server executable"
            )
        self.logger.debug(
            "Server '%s' installation validation successful.", self.server.server_name
        )
        return True

    async def is_installed(self) -> bool:
        """Checks if the server installation is valid asynchronously, without raising exceptions."""
        try:
            return await self.validate_installation()
        except AppFileNotFoundError:
            self.logger.debug(
                "is_installed check: Server '%s' not found or installation invalid (directory or executable missing).",
                self.server.server_name,
            )
            return False
