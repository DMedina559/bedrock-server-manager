import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bedrock_server_manager.web.routers.websocket_router import (
    router as websocket_router,
)
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.web.auth_utils import User, get_current_user

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_user():
    """Provides a mock user for dependency override."""
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
    """Creates a minimal FastAPI app with only the websocket router for isolated testing."""

    # Create a mock AppContext
    mock_context = MagicMock(spec=AppContext)
    mock_context.connection_manager = AsyncMock()
    mock_context.loop = asyncio.get_event_loop()

    app = FastAPI()
    app.state.app_context = mock_context
    app.include_router(websocket_router)

    # Override dependencies
    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    yield app

    app.dependency_overrides.clear()


async def test_websocket_connection_and_auth(test_app):
    """
    Tests that a WebSocket connection is accepted for an authenticated user.
    """
    client = TestClient(test_app)
    try:
        with client.websocket_connect("/ws") as websocket:
            assert websocket
            # The connection manager's connect method should have been called.
            app_context = test_app.state.app_context
            app_context.connection_manager.connect.assert_awaited_once()
    except Exception as e:
        pytest.fail(f"WebSocket connection failed for authenticated user: {e}")


async def test_websocket_subscription(test_app):
    """
    Tests that a client can subscribe and unsubscribe from a topic.
    """
    client = TestClient(test_app)
    app_context = test_app.state.app_context

    # Make the connect method return a specific client_id for predictability
    client_id = "testuser:1234"
    app_context.connection_manager.connect.return_value = client_id

    with client.websocket_connect("/ws") as websocket:
        # Subscribe
        topic = "event:test_subscription"
        websocket.send_json({"action": "subscribe", "topic": topic})
        response = websocket.receive_json()
        assert response["status"] == "success"

        # Check that subscribe was called on the manager
        app_context.connection_manager.subscribe.assert_called_once_with(
            client_id, topic
        )

        # Unsubscribe
        websocket.send_json({"action": "unsubscribe", "topic": topic})
        response = websocket.receive_json()
        assert response["status"] == "success"
        app_context.connection_manager.unsubscribe.assert_called_once_with(
            client_id, topic
        )
