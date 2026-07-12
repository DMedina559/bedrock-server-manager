from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.web.schemas import UserResponse
from bedrock_server_manager.web.websocket_manager import ConnectionManager


@pytest.fixture
def connection_manager():
    return ConnectionManager()


@pytest.fixture
def test_user():
    return UserResponse(
        id=1,
        username="user1",
        identity_type="jwt",
        role="user",
        is_active=True,
        theme="default",
    )


@pytest.fixture
def mock_websocket():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_websocket_connect_disconnect(
    connection_manager, mock_websocket, test_user
):
    """Test connecting and disconnecting a websocket client."""
    client_id = await connection_manager.connect(mock_websocket, test_user)

    assert client_id in connection_manager.active_connections
    assert connection_manager.active_connections[client_id].websocket == mock_websocket
    assert connection_manager.active_connections[client_id].user == test_user

    connection_manager.disconnect(client_id)

    assert client_id not in connection_manager.active_connections


@pytest.mark.asyncio
async def test_websocket_subscribe_unsubscribe(
    connection_manager, mock_websocket, test_user
):
    """Test subscribing and unsubscribing a websocket to topics."""
    client_id = await connection_manager.connect(mock_websocket, test_user)

    connection_manager.subscribe(client_id, "topicA")
    connection_manager.subscribe(client_id, "topicB")

    assert client_id in connection_manager.subscriptions["topicA"]
    assert client_id in connection_manager.subscriptions["topicB"]

    connection_manager.unsubscribe(client_id, "topicA")
    assert client_id not in connection_manager.subscriptions["topicA"]
    assert client_id in connection_manager.subscriptions["topicB"]

    # Disconnecting should also unsubscribe from all topics
    connection_manager.disconnect(client_id)
    assert client_id not in connection_manager.subscriptions["topicB"]


@pytest.mark.asyncio
async def test_websocket_send_to_client(connection_manager, mock_websocket, test_user):
    """Test sending a direct message to a specific client ID."""
    client_id = await connection_manager.connect(mock_websocket, test_user)

    message = {"hello": "world"}
    await connection_manager.send_to_client(message, client_id)

    import json

    mock_websocket.send_text.assert_called_once_with(json.dumps(message))


@pytest.mark.asyncio
async def test_websocket_send_to_user(connection_manager, mock_websocket, test_user):
    """Test sending a message to all websockets of a specific user."""
    mock_websocket2 = MagicMock()
    mock_websocket2.send_text = AsyncMock()

    await connection_manager.connect(mock_websocket, test_user)
    await connection_manager.connect(mock_websocket2, test_user)

    message = {"alert": "update"}
    await connection_manager.send_to_user("user1", message)

    import json

    mock_websocket.send_text.assert_called_once_with(json.dumps(message))
    mock_websocket2.send_text.assert_called_once_with(json.dumps(message))


@pytest.mark.asyncio
async def test_websocket_broadcast_to_topic(
    connection_manager, mock_websocket, test_user
):
    """Test broadcasting a message to a specific topic."""
    mock_ws_unsubscribed = MagicMock()
    mock_ws_unsubscribed.send_text = AsyncMock()

    client_id1 = await connection_manager.connect(mock_websocket, test_user)

    test_user2 = UserResponse(
        id=2,
        username="user2",
        identity_type="jwt",
        role="user",
        is_active=True,
        theme="default",
    )
    await connection_manager.connect(mock_ws_unsubscribed, test_user2)

    connection_manager.subscribe(client_id1, "my_topic")

    message = {"topic_data": 123}
    await connection_manager.broadcast_to_topic("my_topic", message)

    import json

    mock_websocket.send_text.assert_called_once_with(json.dumps(message))
    mock_ws_unsubscribed.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_websocket_broadcast_to_wildcard_topic(
    connection_manager, mock_websocket, test_user
):
    """Test broadcasting a message to wildcard subscriptions."""
    client_id1 = await connection_manager.connect(mock_websocket, test_user)

    connection_manager.subscribe(client_id1, "*")

    message = {"topic_data": 123}
    await connection_manager.broadcast_to_topic("any_random_topic", message)

    import json

    mock_websocket.send_text.assert_called_once_with(json.dumps(message))


@pytest.mark.asyncio
async def test_websocket_disconnect_on_send_error(
    connection_manager, mock_websocket, test_user
):
    """Test that a client is disconnected if sending a message fails."""
    mock_websocket.send_text.side_effect = RuntimeError("WebSocket is not connected")

    client_id = await connection_manager.connect(mock_websocket, test_user)

    await connection_manager.send_to_client({"test": 1}, client_id)

    # Client should be removed from active connections
    assert client_id not in connection_manager.active_connections
