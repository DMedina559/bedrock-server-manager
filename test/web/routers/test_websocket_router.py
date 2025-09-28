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
    # Use a real ConnectionManager to prevent asyncio event loop conflicts
    mock_context.connection_manager = ConnectionManager()

    app = FastAPI()
    app.state.app_context = mock_context
    app.include_router(websocket_router)

    # Override the dependency to bypass token logic
    async def override_get_current_user_for_websocket():
        return mock_user

    app.dependency_overrides[get_current_user_for_websocket] = (
        override_get_current_user_for_websocket
    )

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
            # If the connection is successful, the test passes.
    except Exception as e:
        pytest.fail(f"WebSocket connection failed for authenticated user: {e}")


async def test_websocket_subscription(test_app):
    """
    Tests that a client can subscribe and unsubscribe from a topic.
    """
    client = TestClient(test_app)
    with client.websocket_connect("/ws") as websocket:
        # Subscribe
        topic = "event:test_subscription"
        websocket.send_json({"action": "subscribe", "topic": topic})
        response = websocket.receive_json()
        assert response["status"] == "success"

        # Unsubscribe
        websocket.send_json({"action": "unsubscribe", "topic": topic})
        response = websocket.receive_json()
        assert response["status"] == "success"
