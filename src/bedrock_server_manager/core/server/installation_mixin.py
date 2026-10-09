"""Bedrock installation validation."""

import aiofiles
import aiofiles.os
import aiofiles.ospath

from ...error import AppFileNotFoundError
from .base_server_mixin import BedrockServerBaseMixin


class ServerInstallationMixin(BedrockServerBaseMixin):
    """Checks whether Bedrock files are present and usable."""

    async def validate_installation(self) -> bool:
        """Validates that the server installation directory and executable exist asynchronously."""
        self.logger.debug(
            f"Validating installation for server '{self.server_name}' in directory: {self.server_dir} asynchronously"
        )
        if not await aiofiles.ospath.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")
        if not await aiofiles.ospath.isfile(self.bedrock_executable_path):
            raise AppFileNotFoundError(
                self.bedrock_executable_path, "Server executable"
            )
        self.logger.debug(
            f"Server '{self.server_name}' installation validation successful."
        )
        return True

    async def is_installed(self) -> bool:
        """Checks if the server installation is valid asynchronously, without raising exceptions."""
        try:
            return await self.validate_installation()
        except AppFileNotFoundError:
            self.logger.debug(
                f"is_installed check: Server '{self.server_name}' not found or installation invalid (directory or executable missing)."
            )
            return False
