# bedrock_server_manager/api/websocket.py
"""
Provides API functions for interacting with WebSockets and managing real-time data providers.
"""

import logging

from ..context import AppContext
from ..error import UserInputError
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from .models.websocket import (
    BroadcastRequest,
    BroadcastResponse,
    PublishWsEventRequest,
    PublishWsEventResponse,
    SendToClientRequest,
    SendToClientResponse,
    SendToUserRequest,
    SendToUserResponse,
    UnregisterDataProviderRequest,
    UnregisterDataProviderResponse,
)

logger = logging.getLogger(__name__)


@api_method("websocket_broadcast")
async def broadcast(
    request: BroadcastRequest, *, app_context: AppContext
) -> BroadcastResponse:
    """Broadcasts a JSON payload to all WebSocket clients subscribed to a given topic.

    Accepts BroadcastRequest and returns BroadcastResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    topic = request.topic
    data = request.data
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
            message = {"type": "broadcast", "topic": topic, "data": data}
        await app_context.connection_manager.broadcast_to_topic(topic, message)
        return BroadcastResponse.model_validate(
            {"status": "success", "message": f"Broadcasted to topic '{topic}'"}
        )
    except Exception as e:
        log_operation_error(
            logger, "Failed to broadcast to topic '%s': %s", topic, e, error=e
        )
        raise


@api_method("websocket_send_to_user")
async def send_to_user(
    request: SendToUserRequest, *, app_context: AppContext
) -> SendToUserResponse:
    """Sends a JSON payload to all active WebSocket connections belonging to a user.

    Accepts SendToUserRequest and returns SendToUserResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    username = request.username
    data = request.data
    if not username:
        raise UserInputError("Username cannot be empty.")
    try:
        await app_context.connection_manager.send_to_user(username, data)
        return SendToUserResponse.model_validate(
            {"status": "success", "message": f"Sent message to user '{username}'"}
        )
    except Exception as e:
        log_operation_error(
            logger, "Failed to send to user '%s': %s", username, e, error=e
        )
        raise


@api_method("websocket_send_to_client")
async def send_to_client(
    request: SendToClientRequest, *, app_context: AppContext
) -> SendToClientResponse:
    """Sends a JSON payload directly to a specific connected WebSocket client ID.

    Accepts SendToClientRequest and returns SendToClientResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    client_id = request.client_id
    data = request.data
    if not client_id:
        raise UserInputError("Client ID cannot be empty.")
    try:
        await app_context.connection_manager.send_to_client(data, client_id)
        return SendToClientResponse.model_validate(
            {"status": "success", "message": f"Sent message to client '{client_id}'"}
        )
    except Exception as e:
        log_operation_error(
            logger, "Failed to send to client '%s': %s", client_id, e, error=e
        )
        raise


@api_method("websocket_unregister_data_provider")
async def unregister_data_provider(
    request: UnregisterDataProviderRequest, *, app_context: AppContext
) -> UnregisterDataProviderResponse:
    """Unregisters a data provider handler for a WebSocket topic.

    Accepts UnregisterDataProviderRequest and returns UnregisterDataProviderResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    topic = request.topic
    if not topic:
        raise UserInputError("Topic name cannot be empty.")
    try:
        app_context.connection_manager.unregister_data_provider(topic)
        return UnregisterDataProviderResponse.model_validate(
            {
                "status": "success",
                "message": f"Unregistered data provider for topic '{topic}'",
            }
        )
    except Exception as e:
        log_operation_error(
            logger,
            "Failed to unregister data provider for topic '%s': %s",
            topic,
            e,
            error=e,
        )
        raise


@api_method("websocket_publish_ws_event")
async def publish_ws_event(
    request: PublishWsEventRequest, *, app_context: AppContext
) -> PublishWsEventResponse:
    """Publishes a custom WebSocket event to topic 'ws_event:{event_name}'.

    Accepts PublishWsEventRequest and returns PublishWsEventResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    event_name = request.event_name
    data = request.data
    if not event_name:
        raise UserInputError("Event name cannot be empty.")
    try:
        await app_context.connection_manager.publish_ws_event(event_name, data)
        return PublishWsEventResponse.model_validate(
            {
                "status": "success",
                "message": f"Published WebSocket event '{event_name}'",
            }
        )
    except Exception as e:
        log_operation_error(
            logger, "Failed to publish WebSocket event '%s': %s", event_name, e, error=e
        )
        raise
