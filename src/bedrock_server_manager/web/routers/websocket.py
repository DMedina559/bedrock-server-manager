# bedrock_server_manager/web/routers/websocket_router.py
import asyncio
import inspect
import logging
from typing import Any, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException
from pydantic import ValidationError

from ...context import AppContext
from ...utils import authenticate_websocket_token

router = APIRouter(
    prefix="/ws",
    tags=["WebSocket", "Application"],
)
logger = logging.getLogger(__name__)


async def _call_data_provider(
    handler: Callable[..., Any],
    topic: str,
    request_payload: Any,
    client_id: str,
    user: Any,
) -> Any:
    """Invokes a registered data provider callback with parameter matching."""
    sig = inspect.signature(handler)
    kwargs: dict[str, Any] = {}
    param_names = set(sig.parameters.keys())

    if "topic" in param_names:
        kwargs["topic"] = topic
    if "data" in param_names:
        kwargs["data"] = request_payload
    elif "payload" in param_names:
        kwargs["payload"] = request_payload
    if "client_id" in param_names:
        kwargs["client_id"] = client_id
    if "user" in param_names:
        kwargs["user"] = user

    if not kwargs and len(sig.parameters) > 0:
        params_list = list(sig.parameters.values())
        args = [topic, request_payload, client_id, user][: len(params_list)]
        if asyncio.iscoroutinefunction(handler):
            return await handler(*args)
        return handler(*args)

    if asyncio.iscoroutinefunction(handler):
        return await handler(**kwargs)
    return handler(**kwargs)


@router.websocket("")
async def websocket_endpoint(  # noqa: C901
    websocket: WebSocket,
):
    """
    Handles WebSocket connections.

    Authentication is performed manually on the first message via `authenticate_websocket_token`.
    Clients must send an authentication message within 5 seconds of connecting:
    `{"action": "authenticate", "token": "<your_jwt_token>"}`

    After authentication, clients can send JSON messages to subscribe, unsubscribe, or request data from topics.

    Example messages:
    - `{"action": "subscribe", "topic": "some_topic"}`
    - `{"action": "unsubscribe", "topic": "some_topic"}`
    - `{"action": "request", "topic": "server-status", "data": {}, "request_id": "req-1"}`
    """
    await websocket.accept()
    app_context: AppContext = websocket.app.state.app_context

    # Wait for the first message to authenticate
    try:
        data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        action = data.get("action")

        if action != "authenticate":
            logger.warning("WebSocket auth failed: Missing authentication message")
            await websocket.close(code=1008, reason="Missing authentication message")
            return

        token = data.get("token")
        if not token:
            token = websocket.cookies.get("access_token_cookie")

        if not token:
            logger.warning(
                "WebSocket auth failed: Missing token in payload and cookies"
            )
            await websocket.close(code=1008, reason="Missing token")
            return

        user = await authenticate_websocket_token(app_context, token)

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
    except ValidationError:
        raise
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
                await connection_manager.subscribe(client_id, topic)
                await connection_manager.send_to_client(
                    {
                        "status": "success",
                        "message": f"Subscribed to topic '{topic}'",
                    },
                    client_id,
                )
            elif action == "unsubscribe":
                await connection_manager.unsubscribe(client_id, topic)
                await connection_manager.send_to_client(
                    {
                        "status": "success",
                        "message": f"Unsubscribed from topic '{topic}'",
                    },
                    client_id,
                )
            elif action in ("request", "request_data"):
                request_id = data.get("request_id")
                request_payload = data.get("data")
                handler = connection_manager.get_data_provider(topic)

                if not handler:
                    res: dict[str, Any] = {
                        "status": "error",
                        "type": "response",
                        "topic": topic,
                        "message": f"No data provider registered for topic '{topic}'",
                    }
                    if request_id is not None:
                        res["request_id"] = request_id
                    await connection_manager.send_to_client(res, client_id)
                else:
                    try:
                        result = await _call_data_provider(
                            handler, topic, request_payload, client_id, user
                        )
                        res = {
                            "status": "success",
                            "type": "response",
                            "topic": topic,
                            "data": result,
                        }
                        if request_id is not None:
                            res["request_id"] = request_id
                        await connection_manager.send_to_client(res, client_id)
                    except ValidationError:
                        raise
                    except Exception as e:
                        logger.error(
                            f"Error executing data provider for topic '{topic}': {e}",
                            exc_info=True,
                        )
                        res = {
                            "status": "error",
                            "type": "response",
                            "topic": topic,
                            "message": f"Data provider error: {str(e)}",
                        }
                        if request_id is not None:
                            res["request_id"] = request_id
                        await connection_manager.send_to_client(res, client_id)
            else:
                await connection_manager.send_to_client(
                    {"status": "error", "message": f"Unknown action: '{action}'"},
                    client_id,
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
    except ConnectionResetError:
        logger.info(f"WebSocket client connection reset: {client_id}")
    except RuntimeError as e:
        if "WebSocket is not connected" in str(e):
            logger.info(f"WebSocket client disconnected (RuntimeError): {client_id}")
        else:
            logger.error(
                f"Error in WebSocket for client {client_id}: {e}", exc_info=True
            )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error in WebSocket for client {client_id}: {e}", exc_info=True)
    finally:
        await connection_manager.disconnect(client_id)
