import logging
import re
from typing import Any, Dict

from ..context import AppContext
from ..error import (
    AppFileNotFoundError,
    BSMError,
    InvalidServerNameError,
    UserInputError,
)
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_app_event
from .server import server_lifecycle_manager

logger = logging.getLogger(__name__)


@api_method("get_properties")
def get_properties(server_name: str, app_context: AppContext) -> Dict[str, Any]:
    """Retrieves the current server properties for a given server.

    Args:
        server_name (str): The name of the server.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, Any]: A dictionary containing the parsed server properties.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}
    try:
        server = app_context.get_server(server_name)
        properties = server.get_server_properties()
        raw_content = ""
        with open(server.server_properties_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
        return {
            "status": "success",
            "properties": properties,
            "raw_content": raw_content,
        }
    except AppFileNotFoundError as e:
        return {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to get properties for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get properties: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


@api_method("validate_property_value")
def validate_property_value(  # noqa: C901
    property_name: str, value: str
) -> Dict[str, str]:
    """Validates a specific server property value before it gets applied.

    Args:
        property_name (str): The name of the property to validate.
        value (str): The proposed value for the property.

    Returns:
        Dict[str, str]: A dictionary indicating success or validation error message.
    """
    logger.debug(
        f"API: Validating server property: '{property_name}', Value: '{value}'"
    )
    if value is None:
        value = ""
    # Strings without semicolon
    if property_name in ("server-name", "level-name", "level-seed"):
        if ";" in value:
            return {
                "status": "error",
                "message": f"{property_name} cannot contain semicolons.",
            }
        if property_name == "server-name" and len(value) > 100:
            return {
                "status": "error",
                "message": f"{property_name} is too long (max 100 chars).",
            }
        if property_name == "level-name":
            # level-name has extra file-name invalid character checks typically, but keeping it simpler based on existing regex
            if not re.fullmatch(r"[a-zA-Z0-9_\-]+", value.replace(" ", "_")):
                return {
                    "status": "error",
                    "message": f"{property_name}: use letters, numbers, underscore, hyphen.",
                }
            if len(value) > 80:
                return {
                    "status": "error",
                    "message": f"{property_name} is too long (max 80 chars).",
                }

    # Booleans
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
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'true' or 'false'.",
            }

    # Enums
    elif property_name == "gamemode":
        if value.lower() not in ("survival", "creative", "adventure"):
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'survival', 'creative', or 'adventure'.",
            }
    elif property_name == "difficulty":
        if value.lower() not in ("peaceful", "easy", "normal", "hard"):
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'peaceful', 'easy', 'normal', or 'hard'.",
            }
    elif property_name == "transport":
        if value.lower() not in ("raknet", "nethernet"):
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'raknet' or 'nethernet'.",
            }
    elif property_name == "default-player-permission-level":
        if value.lower() not in ("visitor", "member", "operator"):
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'visitor', 'member', or 'operator'.",
            }
    elif property_name == "content-log-level":
        if value.lower() not in ("error", "warning", "info", "verbose"):
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'error', 'warning', 'info', or 'verbose'.",
            }
    elif property_name == "compression-algorithm":
        if value.lower() not in ("zlib", "snappy"):
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'zlib' or 'snappy'.",
            }
    elif property_name == "chat-restriction":
        if value.lower() not in ("none", "dropped", "disabled"):
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'None', 'Dropped', or 'Disabled'.",
            }
    elif property_name == "script-debugger-auto-attach":
        if value.lower() not in ("disabled", "connect", "listen"):
            return {
                "status": "error",
                "message": f"{property_name}: Must be 'disabled', 'connect', or 'listen'.",
            }

    # Integers with specific ranges
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
                if not (1 <= num_val <= 65535):
                    raise ValueError("Must be a number 1-65535.")
            elif property_name == "max-players":
                if num_val < 1:
                    raise ValueError("Must be a positive integer >= 1.")
            elif property_name == "view-distance":
                if num_val < 5:
                    raise ValueError("Must be an integer >= 5.")
            elif property_name == "tick-distance":
                if not (4 <= num_val <= 12):
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
                if not (0 <= num_val <= 65535):
                    raise ValueError("Must be a number 0-65535.")
            elif property_name == "force-inbound-debug-port":
                if not (1 <= num_val <= 65535):
                    raise ValueError("Must be a number 1-65535.")
            elif property_name in (
                "diagnostics-capture-max-files",
                "diagnostics-capture-max-file-size",
            ):
                if num_val < 1:
                    raise ValueError("Must be a positive integer >= 1.")
        except (ValueError, TypeError) as e:
            return {"status": "error", "message": f"{property_name}: {str(e)}"}

    # Floats / Scalars
    elif property_name in (
        "player-position-acceptance-threshold",
        "player-movement-action-direction-threshold",
        "server-authoritative-block-breaking-pick-range-scalar",
    ):
        try:
            float_val = float(value)
            if property_name == "player-movement-action-direction-threshold":
                if not (0.0 <= float_val <= 1.0):
                    raise ValueError("Must be in range [0, 1].")
        except (ValueError, TypeError) as e:
            msg = str(e) if str(e).startswith("Must") else "Must be a number."
            return {"status": "error", "message": f"{property_name}: {msg}"}

    # Special handling
    elif property_name == "server-build-radius-ratio":
        if value.lower() != "disabled":
            try:
                float_val = float(value)
                if not (0.0 <= float_val <= 1.0):
                    raise ValueError("Must be in range [0.0, 1.0].")
            except (ValueError, TypeError):
                return {
                    "status": "error",
                    "message": f"{property_name}: Must be 'Disabled' or a number in range [0.0, 1.0].",
                }

    return {"status": "success"}


@api_method("set_properties")
@trigger_app_event(before="before_properties_change", after="after_properties_change")
def set_properties(
    server_name: str,
    properties_to_update: Dict[str, str],
    app_context: AppContext,
    restart_after_modify: bool = False,
) -> Dict[str, str]:
    """Sets one or multiple server properties for a given server.

    Args:
        server_name (str): The name of the server.
        properties_to_update (Dict[str, str]): A dictionary of property keys and new values.
        app_context (AppContext): The application context.
        restart_after_modify (bool, optional): Whether to restart the server if running. Defaults to False.

    Returns:
        Dict[str, str]: A dictionary with the status and result message.
    """
    if not server_name:
        raise InvalidServerNameError("Server name required.")
    if not isinstance(properties_to_update, dict):
        raise TypeError("Properties must be a dict.")

    try:
        for name, val_str in properties_to_update.items():
            val_res = validate_property_value(
                name, str(val_str) if val_str is not None else ""
            )
            if val_res.get("status") == "error":
                raise UserInputError(
                    f"Validation failed for '{name}': {val_res.get('message')}"
                )

        with server_lifecycle_manager(
            server_name,
            stop_before=restart_after_modify,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            server = app_context.get_server(server_name)
            for prop_name, prop_value in properties_to_update.items():
                server.set_server_property(prop_name, prop_value)

        return {
            "status": "success",
            "message": "Server properties updated successfully.",
        }

    except (BSMError, FileNotFoundError, UserInputError) as e:
        logger.error(
            f"API: Failed to modify properties for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to modify properties: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error modifying properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}
