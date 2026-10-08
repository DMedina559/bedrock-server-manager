"""
Integration tests for the websocket router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_websocket_missing_auth_action(unauth_client: TestClient):
    with unauth_client.websocket_connect("/ws") as websocket:
        websocket.send_json({"action": "subscribe", "topic": "test"})
        try:
            websocket.receive_json()
            assert False, "Should have disconnected"
        except Exception as e:
            from starlette.websockets import WebSocketDisconnect

            assert isinstance(e, WebSocketDisconnect)
            assert e.code == 1008


def test_websocket_auth_timeout(unauth_client: TestClient):
    with patch("asyncio.wait_for") as mock_wait:
        import asyncio

        mock_wait.side_effect = asyncio.TimeoutError()
        with unauth_client.websocket_connect("/ws") as websocket:
            try:
                websocket.receive_json()
                assert False, "Should have disconnected"
            except Exception as e:
                from starlette.websockets import WebSocketDisconnect

                assert isinstance(e, WebSocketDisconnect)
                assert e.code == 1008


async def test_websocket_auth_success_and_messaging(
    unauth_client: TestClient, app_context, test_user
):
    from bedrock_server_manager.utils import create_access_token

    token = await create_access_token(
        data={"sub": test_user.username}, app_context=app_context
    )

    with unauth_client.websocket_connect("/ws") as websocket:
        websocket.send_json({"action": "authenticate", "token": token})

        # Check success message
        data = websocket.receive_json()
        assert data["status"] == "success"
        assert "Authenticated successfully" in data["message"]

        # Test subscribe
        websocket.send_json({"action": "subscribe", "topic": "test_topic"})
        data = websocket.receive_json()
        assert data["status"] == "success"
        assert "test_topic" in data["message"]

        # Test unsubscribe
        websocket.send_json({"action": "unsubscribe", "topic": "test_topic"})
        data = websocket.receive_json()
        assert data["status"] == "success"
        assert "test_topic" in data["message"]

        # Test invalid action
        websocket.send_json({"action": "foo", "topic": "bar"})
        data = websocket.receive_json()
        assert data["status"] == "error"
        assert data["error"]["code"] == "validation_error"

        # Test missing topic
        websocket.send_json({"action": "subscribe"})
        data = websocket.receive_json()
        assert data["status"] == "error"
        assert "Action and topic are required" in data["message"]


async def test_websocket_auth_via_cookie(
    unauth_client: TestClient, app_context, test_user
):
    from bedrock_server_manager.utils import create_access_token

    token = await create_access_token(
        data={"sub": test_user.username}, app_context=app_context
    )
    unauth_client.cookies.set("access_token_cookie", token)

    with unauth_client.websocket_connect("/ws") as websocket:
        # Note the missing token here, we expect it to fall back to cookie
        websocket.send_json({"action": "authenticate"})

        data = websocket.receive_json()
        assert data["status"] == "success"


async def test_websocket_request_data_success_and_errors(
    unauth_client: TestClient, app_context, test_user
):
    from bedrock_server_manager.utils import create_access_token

    token = await create_access_token(
        data={"sub": test_user.username}, app_context=app_context
    )

    # Register data providers
    async def sample_provider(data, topic):
        return {"response": f"hello {data.get('name')}", "topic": topic}

    async def error_provider():
        raise ValueError("Provider failure")

    app_context.connection_manager.register_data_provider("sample", sample_provider)
    app_context.connection_manager.register_data_provider("failing", error_provider)

    with unauth_client.websocket_connect("/ws") as websocket:
        websocket.send_json({"action": "authenticate", "token": token})
        websocket.receive_json()  # Auth response

        # Test request to unregistered provider
        websocket.send_json(
            {"action": "request", "topic": "unknown_topic", "request_id": "req-1"}
        )
        res = websocket.receive_json()
        assert res["status"] == "error"
        assert res["request_id"] == "req-1"
        assert "No data provider" in res["message"]

        # Test successful request
        websocket.send_json(
            {
                "action": "request",
                "topic": "sample",
                "data": {"name": "World"},
                "request_id": "req-2",
            }
        )
        res = websocket.receive_json()
        assert res["status"] == "success"
        assert res["request_id"] == "req-2"
        assert res["data"] == {"response": "hello World", "topic": "sample"}

        # Test failing provider
        websocket.send_json(
            {"action": "request", "topic": "failing", "request_id": "req-3"}
        )
        res = websocket.receive_json()
        assert res["status"] == "error"
        assert res["request_id"] == "req-3"
        assert "Provider failure" not in res["message"]
        assert res["error"]["code"] == "internal_error"


async def test_websocket_bad_provider_data_returns_safe_error_and_keeps_connection(
    unauth_client, app_context, test_user
):
    from bedrock_server_manager.utils import create_access_token

    async def invalid():
        return {"value": float("nan")}

    app_context.connection_manager.register_data_provider("invalid", invalid)
    token = await create_access_token(
        data={"sub": test_user.username}, app_context=app_context
    )
    with unauth_client.websocket_connect("/ws") as socket:
        socket.send_json({"action": "authenticate", "token": token})
        socket.receive_json()
        socket.send_json(
            {"action": "request", "topic": "invalid", "request_id": "same-id"}
        )
        response = socket.receive_json()
        assert response["request_id"] == "same-id"
        assert response["error"]["code"] == "internal_error"
        socket.send_json(["not", "a", "frame"])
        assert socket.receive_json()["error"]["code"] == "validation_error"
        socket.send_json({"action": "subscribe", "topic": "valid"})
        assert socket.receive_json()["status"] == "success"


async def test_sync_websocket_provider_runs_off_event_loop():
    import threading

    from bedrock_server_manager.web.routers.websocket import _call_data_provider

    def provider():
        return threading.get_ident()

    result = await _call_data_provider(provider, "topic", None, "id", None)
    assert result != threading.get_ident()


async def test_task_subscription_replays_completed_owner_snapshot(
    unauth_client, app_context, test_user
):
    from bedrock_server_manager.utils import create_access_token

    manager = app_context.task_manager

    async def install_result():
        return {"status": "success", "version": "1.26.60.30"}

    task_id = await manager.run_task(install_result, username=test_user.username)
    await manager.shutdown()
    token = await create_access_token(app_context, {"sub": test_user.username})
    with unauth_client.websocket_connect("/ws") as socket:
        socket.send_json({"action": "authenticate", "token": token})
        socket.receive_json()
        socket.send_json({"action": "subscribe", "topic": f"task:{task_id}"})
        assert socket.receive_json()["status"] == "success"
        update = socket.receive_json()
        assert update["type"] == "task_update"
        assert update["topic"] == f"task:{task_id}"
        assert update["data"]["status"] == "completed"
        assert update["data"]["result"]["version"] == "1.26.60.30"
        assert "username" not in update["data"]


async def test_task_subscription_does_not_replay_another_users_snapshot(
    unauth_client, app_context, test_user
):
    from bedrock_server_manager.utils import create_access_token

    task_id = await app_context.task_manager.run_task(lambda: "private", "other")
    await app_context.task_manager.shutdown()
    token = await create_access_token(app_context, {"sub": test_user.username})
    with unauth_client.websocket_connect("/ws") as socket:
        socket.send_json({"action": "authenticate", "token": token})
        socket.receive_json()
        socket.send_json({"action": "subscribe", "topic": f"task:{task_id}"})
        assert socket.receive_json()["status"] == "success"
        socket.send_json({"action": "subscribe", "topic": "next"})
        # The next frame is the acknowledgement, with no intervening private data.
        assert "next" in socket.receive_json()["message"]
