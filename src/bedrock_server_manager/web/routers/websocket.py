# bedrock_server_manager/web/routers/websocket_router.py
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException

from ...context import AppContext
from ..auth_utils import authenticate_websocket_token

router = APIRouter(
    prefix="/ws",
    tags=["WebSocket", "Application"],
)
logger = logging.getLogger(__name__)


@router.websocket("")
async def websocket_endpoint(  # noqa: C901
    websocket: WebSocket,
):
    """
    Handles WebSocket connections.

    Authentication is performed manually on the first message via `authenticate_websocket_token`.
    Clients must send an authentication message within 5 seconds of connecting:
    `{"action": "authenticate", "token": "<your_jwt_token>"}`

    After authentication, clients can send JSON messages to subscribe or unsubscribe from topics.

    Example messages:
    - `{"action": "subscribe", "topic": "some_topic"}`
    - `{"action": "unsubscribe", "topic": "some_topic"}`
    """
    await websocket.accept()
    app_context: AppContext = websocket.app.state.app_context

    # Wait for the first message to authenticate
    try:
        data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        action = data.get("action")
        token = data.get("token")

        if action != "authenticate" or not token:
            logger.warning("WebSocket auth failed: Missing authentication message")
            await websocket.close(code=1008, reason="Missing authentication message")
            return

        user = authenticate_websocket_token(app_context, token)

    except WebSocketDisconnect:
        logger.info("WebSocket auth failed: Client disconnected during authentication")
        return
    except asyncio.TimeoutError:
        logger.warning("WebSocket auth failed: Authentication timeout")
        await websocket.close(code=1008, reason="Authentication timeout")
        return
    except WebSocketException as e:
        logger.warning(f"WebSocket auth failed: {e.reason}")
        await websocket.close(code=e.code, reason=e.reason)
        return
    except Exception as e:
        logger.error(f"WebSocket unexpected auth error: {e}", exc_info=True)
        await websocket.close(code=1008, reason="Internal Authentication Error")
        return

    connection_manager = app_context.connection_manager
    client_id = await connection_manager.connect(websocket, user)

    # Send authentication success response
    await connection_manager.send_to_client(
        {
            "status": "success",
            "message": "Authenticated successfully",
        },
        client_id,
    )

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
    except RuntimeError as e:
        if "WebSocket is not connected" in str(e):
            logger.info(f"WebSocket client disconnected (RuntimeError): {client_id}")
        else:
            logger.error(
                f"Error in WebSocket for client {client_id}: {e}", exc_info=True
            )
    except Exception as e:
        logger.error(f"Error in WebSocket for client {client_id}: {e}", exc_info=True)
    finally:
        connection_manager.disconnect(client_id)
