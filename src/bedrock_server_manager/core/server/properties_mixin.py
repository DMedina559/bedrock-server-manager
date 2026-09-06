import os
import typing
from typing import Any, Dict, Optional

import aiofiles
import aiofiles.ospath

from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from .base_server_mixin import BedrockServerBaseMixin


class ServerPropertiesMixin(BedrockServerBaseMixin):
    """Provides methods for managing the server.properties configuration."""

    def set_server_property(  # noqa: C901
        self, property_key: str, property_value: Any
    ) -> None:
        if not isinstance(property_key, str) or not property_key:
            raise MissingArgumentError(
                "Property key cannot be empty and must be a string."
            )

        str_value = str(property_value)
        if any(ord(c) < 32 for c in str_value if c != "\t"):
            raise UserInputError(
                f"Property value for '{property_key}' contains invalid control characters."
            )

        server_properties_path = self.server_properties_path
        if not os.path.isfile(server_properties_path):
            raise AppFileNotFoundError(server_properties_path, "Server properties file")

        self.logger.debug(
            f"Server '{self.server_name}': Setting property '{property_key}' to '{str_value}' in {server_properties_path}"
        )

        try:
            with open(server_properties_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
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
            if output_lines and not output_lines[-1].endswith("\n"):
                output_lines[-1] += "\n"
            output_lines.append(new_property_line)

        try:
            with open(server_properties_path, "w", encoding="utf-8") as f:
                f.writelines(output_lines)
            self.logger.info(
                f"Successfully set property '{property_key}' for '{self.server_name}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write '{server_properties_path}': {e}"
            ) from e

    def get_server_properties(self) -> Dict[str, str]:
        server_properties_path = self.server_properties_path
        if not os.path.isfile(server_properties_path):
            raise AppFileNotFoundError(server_properties_path, "Server properties file")

        self.logger.debug(
            f"Server '{self.server_name}': Parsing {server_properties_path}"
        )
        properties: Dict[str, str] = {}
        try:
            with open(server_properties_path, "r", encoding="utf-8") as f:
                for line_num, line_content in enumerate(f, 1):
                    line = line_content.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("=", 1)
                    if len(parts) == 2 and parts[0].strip():
                        properties[parts[0].strip()] = parts[1].strip()
                    else:
                        self.logger.warning(
                            f"Skipping malformed line {line_num} in '{server_properties_path}': \"{line}\""
                        )
        except OSError as e:
            raise ConfigParseError(
                f"Failed to read '{server_properties_path}': {e}"
            ) from e

        return properties

    @typing.no_type_check
    async def async_get_server_properties(self) -> Dict[str, str]:
        """Reads the `server.properties` file asynchronously and returns its contents."""

        self.logger.debug(
            f"Reading properties from: {self.server_properties_path} asynchronously"
        )
        if not await aiofiles.ospath.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "server.properties file"
            )

        properties: Dict[str, str] = {}
        try:
            async with aiofiles.open(
                self.server_properties_path, "r", encoding="utf-8"
            ) as file:
                line_num = 1
                async for line in file:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        line_num += 1
                        continue
                    parts = line.split("=", 1)
                    if len(parts) == 2 and parts[0].strip():
                        properties[parts[0].strip()] = parts[1].strip()
                    else:
                        self.logger.warning(
                            f"Skipping malformed line {line_num} in '{self.server_properties_path}': \"{line}\""
                        )
                    line_num += 1
        except OSError as e:
            raise ConfigParseError(
                f"Failed to read properties from {self.server_properties_path}: {e}"
            ) from e

        return properties

    @typing.no_type_check
    async def async_set_server_property(
        self, property_key: str, property_value: Any
    ) -> None:
        """Updates a specific property in `server.properties` asynchronously."""

        if not isinstance(property_key, str) or not property_key:
            raise MissingArgumentError(
                "Property key cannot be empty and must be a string."
            )

        str_value = str(property_value)
        if any(ord(c) < 32 for c in str_value if c != "\t"):
            raise UserInputError(
                f"Property value for '{property_key}' contains invalid control characters."
            )

        self.logger.debug(
            f"Setting property '{property_key}' to '{str_value}' in: {self.server_properties_path} asynchronously"
        )

        if not await aiofiles.ospath.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "server.properties file"
            )

        try:
            async with aiofiles.open(
                self.server_properties_path, "r", encoding="utf-8"
            ) as file:
                lines = await file.readlines()
        except OSError as e:
            raise FileOperationError(
                f"Failed to read '{self.server_properties_path}': {e}"
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
            if output_lines and not output_lines[-1].endswith("\n"):
                output_lines[-1] += "\n"
            output_lines.append(new_property_line)

        try:
            async with aiofiles.open(
                self.server_properties_path, "w", encoding="utf-8"
            ) as file:
                await file.writelines(output_lines)
            self.logger.info(
                f"Successfully set property '{property_key}' for '{self.server_name}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write '{self.server_properties_path}': {e}"
            ) from e

    @typing.no_type_check
    async def async_get_server_property(
        self, property_key: str, default: Optional[Any] = None
    ) -> Optional[Any]:
        """Reads a specific property asynchronously."""
        if not isinstance(property_key, str) or not property_key:
            self.logger.warning(
                f"async_get_server_property called with invalid key: {property_key}. Returning default."
            )
            return default
        try:
            props = await self.async_get_server_properties()
            return props.get(property_key, default)
        except AppFileNotFoundError:
            return default

    def get_server_property(
        self, property_key: str, default: Optional[Any] = None
    ) -> Optional[Any]:
        if not isinstance(property_key, str) or not property_key:
            self.logger.warning(
                f"get_server_property called with invalid key: {property_key}. Returning default."
            )
            return default
        try:
            props = self.get_server_properties()
            return props.get(property_key, default)
        except AppFileNotFoundError:
            return default
