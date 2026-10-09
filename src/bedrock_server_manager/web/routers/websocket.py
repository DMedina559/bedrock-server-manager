# bedrock_server_manager/web/routers/websocket_router.py
import asyncio
import inspect
import logging
from typing import Any, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException
from pydantic import ValidationError

from ...api.errors import error_response
from ...context import AppContext
from ...logging import log_operation_error
from ...utils import authenticate_websocket_token
from ...utils.threads import run_in_thread
from ..schemas.websocket import (
    AuthenticationFrame,
    ClientFrame,
    SocketReply,
    json_payload,
)

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

    args = []
    if not kwargs and len(sig.parameters) > 0:
        args = [topic, request_payload, client_id, user][: len(sig.parameters)]
    if inspect.iscoroutinefunction(handler):
        result = await handler(*args, **kwargs)
    else:
        result = await run_in_thread(handler, *args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
    return json_payload(result).value


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
        auth_frame = AuthenticationFrame.model_validate(data)
        action = auth_frame.action

        if action != "authenticate":
            logger.warning("WebSocket auth failed: Missing authentication message")
            await websocket.close(code=1008, reason="Missing authentication message")
            return

        token = auth_frame.token
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
        logger.debug("WebSocket auth failed: Client disconnected during authentication")
        return
    except asyncio.TimeoutError:
        logger.warning("WebSocket auth failed: Authentication timeout")
        await websocket.close(code=1008, reason="Authentication timeout")
        return
    except WebSocketException as e:
        logger.warning("WebSocket auth failed: %s", e.reason)
        await websocket.close(code=e.code, reason=e.reason)
        return
    except ValidationError:
        await websocket.close(code=1008, reason="Invalid authentication message")
        return
    except Exception as e:
        log_operation_error(logger, "WebSocket unexpected auth error: %s", e, error=e)
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
            if not await connection_manager.refresh_authorization(client_id):
                break
            user = connection_manager.active_connections[client_id].user
            try:
                frame = ClientFrame.model_validate(data)
            except ValidationError as error:
                reply = SocketReply(
                    status="error",
                    message="Action and topic are required and must be valid.",
                    error=error_response(error),
                )
                await connection_manager.send_to_client(
                    reply.model_dump(mode="json", exclude_unset=True), client_id
                )
                continue
            topic = frame.topic
            if frame.action in {"subscribe", "unsubscribe"}:
                if frame.action == "subscribe":
                    await connection_manager.subscribe(client_id, topic)
                    message = f"Subscribed to topic '{topic}'"
                else:
                    await connection_manager.unsubscribe(client_id, topic)
                    message = f"Unsubscribed from topic '{topic}'"
                reply = SocketReply(status="success", message=message)
            else:
                handler = connection_manager.get_data_provider(topic)
                if handler is None:
                    reply = SocketReply(
                        status="error",
                        type="response",
                        topic=topic,
                        request_id=frame.request_id,
                        message=f"No data provider registered for topic '{topic}'",
                    )
                else:
                    try:
                        result = await _call_data_provider(
                            handler, topic, frame.data, client_id, user
                        )
                        reply = SocketReply(
                            status="success",
                            type="response",
                            topic=topic,
                            request_id=frame.request_id,
                            data=result,
                        )
                    except Exception as error:
                        log_operation_error(
                            logger,
                            "Error executing WebSocket data provider for topic %s",
                            topic,
                            error=error,
                        )
                        safe = error_response(error)
                        reply = SocketReply(
                            status="error",
                            type="response",
                            topic=topic,
                            request_id=frame.request_id,
                            message=safe.message,
                            error=safe,
                        )
            await connection_manager.send_to_client(
                reply.model_dump(mode="json", exclude_unset=True), client_id
            )
            # Replay the owner's current snapshot after acknowledging subscription.
            # Fast tasks may finish before the client receives their task ID.
            if frame.action == "subscribe" and topic.startswith("task:"):
                task = await app_context.task_manager.get_task(
                    topic.removeprefix("task:"), username=user.username
                )
                if task is not None:
                    await connection_manager.send_to_client(
                        {
                            "type": "task_update",
                            "topic": topic,
                            "data": task.model_dump(mode="json"),
                        },
                        client_id,
                    )

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected: %s", client_id)
    except ConnectionResetError:
        logger.debug("WebSocket client connection reset: %s", client_id)
    except RuntimeError as e:
        if "WebSocket is not connected" in str(e):
            logger.debug("WebSocket client disconnected (RuntimeError): %s", client_id)
        else:
            log_operation_error(
                logger, "Error in WebSocket for client %s: %s", client_id, e, error=e
            )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "Error in WebSocket for client %s: %s", client_id, e, error=e
        )
    finally:
        await connection_manager.disconnect(client_id)
