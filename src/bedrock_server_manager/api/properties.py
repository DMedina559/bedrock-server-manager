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
        return {"status": "success", "properties": properties}
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
    if property_name == "server-name":
        if ";" in value:
            return {
                "status": "error",
                "message": "server-name cannot contain semicolons.",
            }
        if len(value) > 100:
            return {
                "status": "error",
                "message": "server-name is too long (max 100 chars).",
            }
    elif property_name == "level-name":
        if not re.fullmatch(r"[a-zA-Z0-9_\-]+", value.replace(" ", "_")):
            return {
                "status": "error",
                "message": "level-name: use letters, numbers, underscore, hyphen.",
            }
        if len(value) > 80:
            return {
                "status": "error",
                "message": "level-name is too long (max 80 chars).",
            }
    elif property_name in ("server-port", "server-portv6"):
        try:
            port = int(value)
            if not (1024 <= port <= 65535):
                raise ValueError()
        except (ValueError, TypeError):
            return {
                "status": "error",
                "message": f"{property_name}: must be a number 1024-65535.",
            }
    elif property_name in ("max-players", "view-distance", "tick-distance"):
        try:
            num_val = int(value)
            if property_name == "max-players" and num_val < 1:
                raise ValueError("Must be >= 1")
            if property_name == "view-distance" and num_val < 5:
                raise ValueError("Must be >= 5")
            if property_name == "tick-distance" and not (4 <= num_val <= 12):
                raise ValueError("Must be between 4-12")
        except (ValueError, TypeError):
            range_msg = "a positive number"
            if property_name == "view-distance":
                range_msg = "a number >= 5"
            if property_name == "tick-distance":
                range_msg = "a number between 4 and 12"
            msg = f"Invalid value for '{property_name}'. Must be {range_msg}."
            return {"status": "error", "message": msg}
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
