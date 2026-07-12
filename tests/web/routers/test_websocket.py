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


def test_websocket_auth_success_and_messaging(
    unauth_client: TestClient, app_context, test_user
):
    from bedrock_server_manager.utils import create_access_token

    token = create_access_token(
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
        assert "Unknown action" in data["message"]

        # Test missing topic
        websocket.send_json({"action": "subscribe"})
        data = websocket.receive_json()
        assert data["status"] == "error"
        assert "Action and topic are required" in data["message"]


def test_websocket_auth_via_cookie(unauth_client: TestClient, app_context, test_user):
    from bedrock_server_manager.utils import create_access_token

    token = create_access_token(
        data={"sub": test_user.username}, app_context=app_context
    )
    unauth_client.cookies.set("access_token_cookie", token)

    with unauth_client.websocket_connect("/ws") as websocket:
        # Note the missing token here, we expect it to fall back to cookie
        websocket.send_json({"action": "authenticate"})

        data = websocket.receive_json()
        assert data["status"] == "success"
