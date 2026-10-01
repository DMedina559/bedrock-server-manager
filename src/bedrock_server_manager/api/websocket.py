# bedrock_server_manager/api/websocket.py
"""
Provides API functions for interacting with WebSockets and managing real-time data providers.
"""

import logging
from typing import Any, Callable, Dict, Optional

from ..context import AppContext
from ..error import UserInputError
from ..plugins.api_bridge import api_method

logger = logging.getLogger(__name__)


@api_method("websocket_broadcast")
async def broadcast(
    topic: str,
    data: Any,
    app_context: AppContext,
) -> Dict[str, Any]:
    """
    Broadcasts a JSON payload to all WebSocket clients subscribed to a given topic.

    Args:
        topic (str): The target topic name.
        data (Any): JSON-serializable payload to send.
        app_context (AppContext): Application context.

    Returns:
        Dict[str, Any]: Standard operation result.
    """
    if not topic:
        raise UserInputError("Topic name cannot be empty.")

    try:
        if (
            isinstance(data, dict)
            and "topic" in data
            and ("data" in data or "type" in data)
        ):
            message = data
        else:
            message = {
                "type": "broadcast",
                "topic": topic,
                "data": data,
            }
        await app_context.connection_manager.broadcast_to_topic(topic, message)
        return {"status": "success", "message": f"Broadcasted to topic '{topic}'"}
    except Exception as e:
        logger.error(f"Failed to broadcast to topic '{topic}': {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to broadcast: {e}"}


@api_method("websocket_send_to_user")
async def send_to_user(
    username: str,
    data: Any,
    app_context: AppContext,
) -> Dict[str, Any]:
    """
    Sends a JSON payload to all active WebSocket connections belonging to a user.

    Args:
        username (str): The target username.
        data (Any): JSON-serializable payload to send.
        app_context (AppContext): Application context.

    Returns:
        Dict[str, Any]: Standard operation result.
    """
    if not username:
        raise UserInputError("Username cannot be empty.")

    try:
        await app_context.connection_manager.send_to_user(username, data)
        return {"status": "success", "message": f"Sent message to user '{username}'"}
    except Exception as e:
        logger.error(f"Failed to send to user '{username}': {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send to user: {e}"}


@api_method("websocket_send_to_client")
async def send_to_client(
    client_id: str,
    data: Any,
    app_context: AppContext,
) -> Dict[str, Any]:
    """
    Sends a JSON payload directly to a specific connected WebSocket client ID.

    Args:
        client_id (str): Unique WebSocket client identifier.
        data (Any): JSON-serializable payload to send.
        app_context (AppContext): Application context.

    Returns:
        Dict[str, Any]: Standard operation result.
    """
    if not client_id:
        raise UserInputError("Client ID cannot be empty.")

    try:
        await app_context.connection_manager.send_to_client(data, client_id)
        return {"status": "success", "message": f"Sent message to client '{client_id}'"}
    except Exception as e:
        logger.error(f"Failed to send to client '{client_id}': {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send to client: {e}"}


@api_method("websocket_register_data_provider")
async def register_data_provider(
    topic: str,
    handler: Callable[..., Any],
    app_context: AppContext,
    plugin_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Registers a data provider handler for a WebSocket topic.

    Args:
        topic (str): The topic name (e.g. 'server-status').
        handler (Callable): Async or sync function to handle requests for this topic.
        app_context (AppContext): Application context.
        plugin_name (Optional[str]): Name of registering plugin.

    Returns:
        Dict[str, Any]: Standard operation result.
    """
    if not topic:
        raise UserInputError("Topic name cannot be empty.")
    if not callable(handler):
        raise UserInputError("Data provider handler must be callable.")

    if not plugin_name:
        bound_self = getattr(handler, "__self__", None)
        if bound_self:
            api = getattr(bound_self, "api", None)
            plugin_name = getattr(api, "_plugin_name", None) or getattr(
                bound_self, "name", None
            )

    try:
        app_context.connection_manager.register_data_provider(
            topic=topic, handler=handler, plugin_name=plugin_name
        )
        return {
            "status": "success",
            "message": f"Data provider registered for topic '{topic}'",
        }
    except Exception as e:
        logger.error(
            f"Failed to register data provider for topic '{topic}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to register data provider: {e}"}


@api_method("websocket_unregister_data_provider")
async def unregister_data_provider(
    topic: str,
    app_context: AppContext,
) -> Dict[str, Any]:
    """
    Unregisters a data provider handler for a WebSocket topic.

    Args:
        topic (str): The topic name to unregister.
        app_context (AppContext): Application context.

    Returns:
        Dict[str, Any]: Standard operation result.
    """
    if not topic:
        raise UserInputError("Topic name cannot be empty.")

    try:
        app_context.connection_manager.unregister_data_provider(topic)
        return {
            "status": "success",
            "message": f"Unregistered data provider for topic '{topic}'",
        }
    except Exception as e:
        logger.error(
            f"Failed to unregister data provider for topic '{topic}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to unregister data provider: {e}",
        }


@api_method("websocket_publish_ws_event")
async def publish_ws_event(
    event_name: str,
    data: Any,
    app_context: AppContext,
) -> Dict[str, Any]:
    """
    Publishes a custom WebSocket event to topic 'ws_event:{event_name}'.

    Args:
        event_name (str): Custom event name.
        data (Any): Event data payload.
        app_context (AppContext): Application context.

    Returns:
        Dict[str, Any]: Standard operation result.
    """
    if not event_name:
        raise UserInputError("Event name cannot be empty.")

    try:
        await app_context.connection_manager.publish_ws_event(event_name, data)
        return {
            "status": "success",
            "message": f"Published WebSocket event '{event_name}'",
        }
    except Exception as e:
        logger.error(
            f"Failed to publish WebSocket event '{event_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to publish WebSocket event: {e}"}
