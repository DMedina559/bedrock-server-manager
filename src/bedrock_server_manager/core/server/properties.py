"""Bedrock properties component."""

from typing import TYPE_CHECKING, Any, Dict, Optional

import aiofiles.ospath

from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from ...utils.io import load_lines, save_lines

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerProperties:
    """Properties operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server

    async def get_server_properties(self) -> Dict[str, str]:
        """Reads the `server.properties` file asynchronously and returns its contents."""
        server_properties_path = self.server.paths.server_properties_path
        if not await aiofiles.ospath.isfile(server_properties_path):
            raise AppFileNotFoundError(server_properties_path, "Server properties file")
        self.server.logger.debug(
            f"Server '{self.server.server_name}': Parsing {server_properties_path} asynchronously"
        )
        properties: Dict[str, str] = {}
        try:
            lines = await load_lines(server_properties_path)
            for line_num, line_content in enumerate(lines, 1):
                line = line_content.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                if len(parts) == 2 and parts[0].strip():
                    properties[parts[0].strip()] = parts[1].strip()
                else:
                    self.server.logger.warning(
                        f'''Skipping malformed line {line_num} in '{server_properties_path}': "{line}"'''
                    )
        except OSError as e:
            raise ConfigParseError(
                f"Failed to read '{server_properties_path}': {e}"
            ) from e
        return properties

    async def set_server_property(self, property_key: str, property_value: Any) -> None:
        """Updates a specific property in `server.properties` asynchronously."""
        async with self.server.get_file_lock(self.server.paths.server_properties_path):
            if not isinstance(property_key, str) or not property_key:
                raise MissingArgumentError(
                    "Property key cannot be empty and must be a string."
                )
            str_value = str(property_value)
            if any((ord(c) < 32 for c in str_value if c != "\t")):
                raise UserInputError(
                    f"Property value for '{property_key}' contains invalid control characters."
                )
            server_properties_path = self.server.paths.server_properties_path
            if not await aiofiles.ospath.isfile(server_properties_path):
                raise AppFileNotFoundError(
                    server_properties_path, "Server properties file"
                )
            self.server.logger.debug(
                f"Server '{self.server.server_name}': Setting property '{property_key}' to '{str_value}' in {server_properties_path} asynchronously"
            )
            try:
                lines = await load_lines(server_properties_path)
            except OSError as e:
                raise FileOperationError(
                    f"Failed to read '{server_properties_path}': {e}"
                ) from e
            output_lines = []
            property_found_and_set = False
            new_property_line = f"{property_key}={str_value}\n"
            for line_content in lines:
                stripped_line = line_content.strip()
                if not stripped_line or stripped_line.startswith("#"):
                    output_lines.append(line_content)
                    continue
                if stripped_line.startswith(property_key + "="):
                    if not property_found_and_set:
                        output_lines.append(new_property_line)
                        property_found_and_set = True
                    else:
                        output_lines.append("# DUPLICATE IGNORED: " + line_content)
                else:
                    output_lines.append(line_content)
            if not property_found_and_set:
                if output_lines and (not output_lines[-1].endswith("\n")):
                    output_lines[-1] += "\n"
                output_lines.append(new_property_line)
            try:
                lock = self.server.get_file_lock(server_properties_path)
                async with lock:
                    await save_lines(output_lines, server_properties_path)
                self.server.logger.info(
                    f"Successfully set property '{property_key}' for '{self.server.server_name}'."
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write '{server_properties_path}': {e}"
                ) from e

    async def get_server_property(
        self, property_key: str, default: Optional[Any] = None
    ) -> Optional[Any]:
        """Reads a specific property asynchronously."""
        if not isinstance(property_key, str) or not property_key:
            self.server.logger.warning(
                f"get_server_property called with invalid key: {property_key}. Returning default."
            )
            return default
        try:
            props = await self.get_server_properties()
            return props.get(property_key, default)
        except AppFileNotFoundError:
            return default
