import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.web.auth_utils import User
from bedrock_server_manager.web.routers.websocket_router import (
    router as websocket_router,
)
from bedrock_server_manager.web.websocket_manager import ConnectionManager

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_user():
    return User(
        id="1",
        username="testuser",
        role="admin",
        hashed_password="abc",
        identity_type="local",
        is_active=True,
        theme="dark",
    )


@pytest.fixture
def test_app_context():
    mock_context = MagicMock(spec=AppContext)
    mock_context.connection_manager = ConnectionManager()
    # Mock settings needed for get_jwt_secret_key if auth was real, but we mock auth
    mock_context.settings = MagicMock()
    return mock_context


@pytest.fixture
def test_app(test_app_context):
    app = FastAPI()
    app.state.app_context = test_app_context
    app.include_router(websocket_router)
    return app


async def test_send_to_user_integration(test_app, test_app_context, mock_user):
    """
    Tests if the ConnectionManager can send a message to a specific user
    who has an active WebSocket connection.
    """
    client = TestClient(test_app)

    # Use AsyncMock because the function is awaited
    with patch(
        "bedrock_server_manager.web.routers.websocket_router.get_current_user_for_websocket",
        new_callable=AsyncMock,
    ) as mock_auth:
        mock_auth.return_value = mock_user

        with client.websocket_connect("/ws") as websocket:
            # Verify auth was called
            mock_auth.assert_called_once()

            # Give a moment for the connection to be fully registered.
            await asyncio.sleep(0.01)

            # Simulate the backend wanting to send a message to this user.
            test_message = {"data": "hello testuser"}
            await test_app_context.connection_manager.send_to_user(
                "testuser", test_message
            )

            # Assert that the client received the message.
            received_message = websocket.receive_json()
            assert received_message == test_message


async def test_wildcard_subscription(test_app, test_app_context, mock_user):
    """
    Tests that a client subscribed to '*' receives messages from other topics.
    """
    client = TestClient(test_app)

    with patch(
        "bedrock_server_manager.web.routers.websocket_router.get_current_user_for_websocket",
        new_callable=AsyncMock,
    ) as mock_auth:
        mock_auth.return_value = mock_user

        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"action": "subscribe", "topic": "*"})
            confirmation = websocket.receive_json()
            assert confirmation["status"] == "success"

            await asyncio.sleep(0.01)

            test_message = {"data": "broadcast message"}
            await test_app_context.connection_manager.broadcast_to_topic(
                "event:some_event", test_message
            )

            received_message = websocket.receive_json()
            assert received_message == test_message
