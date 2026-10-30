"""Bedrock properties component."""

import logging
import math
import re
from typing import TYPE_CHECKING, Any, Dict, Optional

import aiofiles.ospath

from ...api.models.properties import (
    ValidatePropertyValueRequest,
    ValidatePropertyValueResponse,
)
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

logger = logging.getLogger(__name__)


def validate_property_value(
    request: ValidatePropertyValueRequest,
) -> ValidatePropertyValueResponse:
    """Validates a specific server property value before it gets applied."""
    property_name = request.property_name
    value = request.value
    logger.debug("Validating server property '%s'.", property_name)
    if value is None:
        value = ""
    if property_name in ("server-name", "level-name", "level-seed"):
        if ";" in value:
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name} cannot contain semicolons.",
                }
            )
        if property_name == "server-name" and len(value) > 100:
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name} is too long (max 100 chars).",
                }
            )
        if property_name == "level-name":
            if not re.fullmatch("[a-zA-Z0-9_\\-]+", value.replace(" ", "_")):
                return ValidatePropertyValueResponse.model_validate(
                    {
                        "status": "success",
                        "valid": False,
                        "message": f"{property_name}: use letters, numbers, underscore, hyphen.",
                    }
                )
            if len(value) > 80:
                return ValidatePropertyValueResponse.model_validate(
                    {
                        "status": "success",
                        "valid": False,
                        "message": f"{property_name} is too long (max 80 chars).",
                    }
                )
    elif property_name in (
        "force-gamemode",
        "allow-cheats",
        "online-mode",
        "allow-list",
        "enable-lan-visibility",
        "texturepack-required",
        "content-log-file-enabled",
        "content-log-console-output-enabled",
        "server-authoritative-movement-strict",
        "server-authoritative-dismount-strict",
        "server-authoritative-entity-interactions-strict",
        "disable-player-interaction",
        "client-side-chunk-generation-enabled",
        "block-network-ids-are-hashes",
        "disable-persona",
        "disable-custom-skins",
        "allow-outbound-script-debugging",
        "allow-inbound-script-debugging",
        "script-watchdog-enable",
        "script-watchdog-enable-exception-handling",
        "script-watchdog-enable-shutdown",
        "script-watchdog-hang-exception",
        "diagnostics-capture-auto-start",
        "disable-client-vibrant-visuals",
        "enable-profiler",
        "enable-editor-network-metrics",
        "convert-world-to-editor-project",
        "allow-player-joining",
    ):
        if value.lower() not in ("true", "false"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'true' or 'false'.",
                }
            )
    elif property_name == "gamemode":
        if value.lower() not in ("survival", "creative", "adventure"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'survival', 'creative', or 'adventure'.",
                }
            )
    elif property_name == "difficulty":
        if value.lower() not in ("peaceful", "easy", "normal", "hard"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'peaceful', 'easy', 'normal', or 'hard'.",
                }
            )
    elif property_name == "transport":
        if value.lower() not in ("raknet", "nethernet"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'raknet' or 'nethernet'.",
                }
            )
    elif property_name == "default-player-permission-level":
        if value.lower() not in ("visitor", "member", "operator"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'visitor', 'member', or 'operator'.",
                }
            )
    elif property_name == "content-log-level":
        if value.lower() not in ("error", "warning", "info", "verbose"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'error', 'warning', 'info', or 'verbose'.",
                }
            )
    elif property_name == "compression-algorithm":
        if value.lower() not in ("zlib", "snappy"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'zlib' or 'snappy'.",
                }
            )
    elif property_name == "chat-restriction":
        if value.lower() not in ("none", "dropped", "disabled"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'None', 'Dropped', or 'Disabled'.",
                }
            )
    elif property_name == "script-debugger-auto-attach":
        if value.lower() not in ("disabled", "connect", "listen"):
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: Must be 'disabled', 'connect', or 'listen'.",
                }
            )
    elif property_name in (
        "server-port",
        "server-portv6",
        "max-players",
        "view-distance",
        "tick-distance",
        "player-idle-timeout",
        "max-threads",
        "compression-threshold",
        "force-inbound-debug-port",
        "script-watchdog-timeout",
        "script-watchdog-hang-threshold",
        "script-watchdog-spike-threshold",
        "script-watchdog-slow-threshold",
        "script-watchdog-memory-warning",
        "script-watchdog-memory-limit",
        "script-debugger-auto-attach-timeout",
        "diagnostics-capture-max-files",
        "diagnostics-capture-max-file-size",
        "sentry-rate-limit-window",
        "sentry-max-events-per-window",
    ):
        try:
            num_val = int(value)
            if property_name in ("server-port", "server-portv6"):
                if not 1 <= num_val <= 65535:
                    raise ValueError("Must be a number 1-65535.")
            elif property_name == "max-players":
                if num_val < 1:
                    raise ValueError("Must be a positive integer >= 1.")
            elif property_name == "view-distance":
                if num_val < 5:
                    raise ValueError("Must be an integer >= 5.")
            elif property_name == "tick-distance":
                if not 4 <= num_val <= 12:
                    raise ValueError("Must be between 4 and 12.")
            elif property_name in (
                "player-idle-timeout",
                "script-debugger-auto-attach-timeout",
                "script-watchdog-hang-threshold",
                "script-watchdog-spike-threshold",
                "script-watchdog-slow-threshold",
                "script-watchdog-memory-warning",
                "script-watchdog-memory-limit",
                "sentry-rate-limit-window",
                "sentry-max-events-per-window",
                "max-threads",
            ):
                if num_val < 0:
                    raise ValueError("Must be a non-negative integer.")
            elif property_name == "compression-threshold":
                if not 0 <= num_val <= 65535:
                    raise ValueError("Must be a number 0-65535.")
            elif property_name == "force-inbound-debug-port":
                if not 1 <= num_val <= 65535:
                    raise ValueError("Must be a number 1-65535.")
            elif property_name in (
                "diagnostics-capture-max-files",
                "diagnostics-capture-max-file-size",
            ):
                if num_val < 1:
                    raise ValueError("Must be a positive integer >= 1.")
        except (ValueError, TypeError) as e:
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: {str(e)}",
                }
            )
    elif property_name in (
        "player-position-acceptance-threshold",
        "player-movement-action-direction-threshold",
        "server-authoritative-block-breaking-pick-range-scalar",
    ):
        try:
            float_val = float(value)
            if not math.isfinite(float_val):
                raise ValueError("Must be a finite number.")
            if property_name == "player-movement-action-direction-threshold":
                if not 0.0 <= float_val <= 1.0:
                    raise ValueError("Must be in range [0, 1].")
        except (ValueError, TypeError) as e:
            msg = str(e) if str(e).startswith("Must") else "Must be a number."
            return ValidatePropertyValueResponse.model_validate(
                {
                    "status": "success",
                    "valid": False,
                    "message": f"{property_name}: {msg}",
                }
            )
    elif property_name == "server-build-radius-ratio":
        if value.lower() != "disabled":
            try:
                float_val = float(value)
                if not 0.0 <= float_val <= 1.0:
                    raise ValueError("Must be in range [0.0, 1.0].")
            except (ValueError, TypeError):
                return ValidatePropertyValueResponse.model_validate(
                    {
                        "status": "success",
                        "valid": False,
                        "message": f"{property_name}: Must be 'Disabled' or a number in range [0.0, 1.0].",
                    }
                )
    return ValidatePropertyValueResponse.model_validate(
        {"status": "success", "valid": True, "message": None}
    )


def _validate_properties_payload(properties_to_update: Dict[str, Any]) -> None:
    """Validate a dictionary of server property updates, raising UserInputError on failure."""
    for name, val_str in properties_to_update.items():
        val_res = validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name=name,
                value=str(val_str) if val_str is not None else "",
            )
        )
        if not val_res.valid:
            raise UserInputError(f"Validation failed for '{name}': {val_res.message}")


class ServerProperties:
    """Properties operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__), {"server_name": server.server_name}
        )

    async def get_server_properties(self) -> Dict[str, str]:
        """Reads the ``server.properties`` file asynchronously and returns its contents."""
        server_properties_path = self.server.paths.server_properties_path
        if not await aiofiles.ospath.isfile(server_properties_path):
            raise AppFileNotFoundError(server_properties_path, "Server properties file")
        self.logger.debug(
            "Server '%s': Parsing %s", self.server.server_name, server_properties_path
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
                    self.logger.warning(
                        "Skipping malformed property at line %s in '%s'.",
                        line_num,
                        server_properties_path,
                    )
        except OSError as e:
            raise ConfigParseError(
                f"Failed to read '{server_properties_path}': {e}"
            ) from e
        return properties

    async def set_server_property(self, property_key: str, property_value: Any) -> None:
        """Updates a specific property in ``server.properties`` asynchronously."""
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
            self.logger.debug(
                "Updating property '%s' for server '%s'.",
                property_key,
                self.server.server_name,
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
                await save_lines(output_lines, server_properties_path)
                self.logger.info(
                    "Successfully set property '%s' for '%s'.",
                    property_key,
                    self.server.server_name,
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
            self.logger.warning(
                "get_server_property called with invalid key: %s. Returning default.",
                property_key,
            )
            return default
        try:
            props = await self.get_server_properties()
            return props.get(property_key, default)
        except AppFileNotFoundError:
            return default
