# bedrock_server_manager/web/routers/websocket_router.py
import logging
import uuid
from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect

from ..auth_utils import User, get_current_user_for_websocket
from ...context import AppContext

router = APIRouter(
    prefix="/ws",
    tags=["websockets"],
)
logger = logging.getLogger(__name__)


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    user: User = Depends(get_current_user_for_websocket),
):
    """
    Handles WebSocket connections.

    Authentication is performed via the `get_current_user` dependency.
    Clients can send JSON messages to subscribe or unsubscribe from topics.

    Example messages:
    - `{"action": "subscribe", "topic": "some_topic"}`
    - `{"action": "unsubscribe", "topic": "some_topic"}`
    """
    app_context: AppContext = websocket.app.state.app_context
    connection_manager = app_context.connection_manager
    client_id = await connection_manager.connect(websocket, user)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            topic = data.get("topic")

            if not action or not topic:
                await connection_manager.send_to_client(
                    {"status": "error", "message": "Action and topic are required."},
                    client_id,
                )
                continue

            if action == "subscribe":
                connection_manager.subscribe(client_id, topic)
                await connection_manager.send_to_client(
                    {
                        "status": "success",
                        "message": f"Subscribed to topic '{topic}'",
                    },
                    client_id,
                )
            elif action == "unsubscribe":
                connection_manager.unsubscribe(client_id, topic)
                await connection_manager.send_to_client(
                    {
                        "status": "success",
                        "message": f"Unsubscribed from topic '{topic}'",
                    },
                    client_id,
                )
            else:
                await connection_manager.send_to_client(
                    {"status": "error", "message": f"Unknown action: '{action}'"},
                    client_id,
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket for client {client_id}: {e}", exc_info=True)
    finally:
        connection_manager.disconnect(client_id)
