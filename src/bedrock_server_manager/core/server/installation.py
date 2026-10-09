"""Bedrock installation component."""

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

    async def validate_installation(self) -> bool:
        """Validates that the server installation directory and executable exist asynchronously."""
        self.server.logger.debug(
            f"Validating installation for server '{self.server.server_name}' in directory: {self.server.paths.server_dir} asynchronously"
        )
        if not await aiofiles.ospath.isdir(self.server.paths.server_dir):
            raise AppFileNotFoundError(self.server.paths.server_dir, "Server directory")
        if not await aiofiles.ospath.isfile(self.server.paths.bedrock_executable_path):
            raise AppFileNotFoundError(
                self.server.paths.bedrock_executable_path, "Server executable"
            )
        self.server.logger.debug(
            f"Server '{self.server.server_name}' installation validation successful."
        )
        return True

    async def is_installed(self) -> bool:
        """Checks if the server installation is valid asynchronously, without raising exceptions."""
        try:
            return await self.validate_installation()
        except AppFileNotFoundError:
            self.server.logger.debug(
                f"is_installed check: Server '{self.server.server_name}' not found or installation invalid (directory or executable missing)."
            )
            return False
