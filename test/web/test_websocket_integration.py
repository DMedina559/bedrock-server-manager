import pytest
import asyncio
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bedrock_server_manager.web.routers.websocket_router import (
    router as websocket_router,
)
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.web.auth_utils import User, get_current_user_for_websocket
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
    )


@pytest.fixture
def test_app(mock_user):
    app = FastAPI()
    mock_context = MagicMock(spec=AppContext)
    # Use a real ConnectionManager to test its functionality
    mock_context.connection_manager = ConnectionManager()

    app.state.app_context = mock_context
    app.include_router(websocket_router)

    async def override_get_current_user_for_websocket():
        return mock_user

    app.dependency_overrides[get_current_user_for_websocket] = (
        override_get_current_user_for_websocket
    )
    yield app
    app.dependency_overrides.clear()


async def test_send_to_user_integration(test_app):
    """
    Tests if the ConnectionManager can send a message to a specific user
    who has an active WebSocket connection.
    """
    client = TestClient(test_app)
    app_context = test_app.state.app_context

    with client.websocket_connect("/ws") as websocket:
        # At this point, the user "testuser" is connected.
        # The connection_manager now holds their connection info.

        # Give a moment for the connection to be fully registered.
        await asyncio.sleep(0.01)

        # Simulate the backend wanting to send a message to this user.
        test_message = {"data": "hello testuser"}
        await app_context.connection_manager.send_to_user("testuser", test_message)

        # Assert that the client received the message.
        received_message = websocket.receive_json()
        assert received_message == test_message
