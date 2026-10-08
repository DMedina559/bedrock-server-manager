import asyncio
from types import SimpleNamespace
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


async def test_websocket_connect_disconnect(
    connection_manager, mock_websocket, test_user
):
    """Test connecting and disconnecting a websocket client."""
    client_id = await connection_manager.connect(mock_websocket, test_user)

    assert client_id in connection_manager.active_connections
    assert connection_manager.active_connections[client_id].websocket == mock_websocket
    assert connection_manager.active_connections[client_id].user == test_user

    await connection_manager.disconnect(client_id)

    assert client_id not in connection_manager.active_connections


async def test_websocket_subscribe_unsubscribe(
    connection_manager, mock_websocket, test_user
):
    """Test subscribing and unsubscribing a websocket to topics."""
    client_id = await connection_manager.connect(mock_websocket, test_user)

    await connection_manager.subscribe(client_id, "topicA")
    await connection_manager.subscribe(client_id, "topicB")

    assert client_id in connection_manager.subscriptions["topicA"]
    assert client_id in connection_manager.subscriptions["topicB"]

    await connection_manager.unsubscribe(client_id, "topicA")
    assert "topicA" not in connection_manager.subscriptions
    assert client_id in connection_manager.subscriptions["topicB"]

    # Disconnecting should also unsubscribe from all topics
    await connection_manager.disconnect(client_id)
    assert "topicB" not in connection_manager.subscriptions


async def test_websocket_send_to_client(connection_manager, mock_websocket, test_user):
    """Test sending a direct message to a specific client ID."""
    client_id = await connection_manager.connect(mock_websocket, test_user)

    message = {"hello": "world"}
    await connection_manager.send_to_client(message, client_id)

    import json

    mock_websocket.send_text.assert_called_once_with(json.dumps(message))


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

    await connection_manager.subscribe(client_id1, "my_topic")

    message = {"topic_data": 123}
    await connection_manager.broadcast_to_topic("my_topic", message)

    import json

    mock_websocket.send_text.assert_called_once_with(json.dumps(message))
    mock_ws_unsubscribed.send_text.assert_not_called()


async def test_websocket_broadcast_to_wildcard_topic(
    connection_manager, mock_websocket, test_user
):
    """Test broadcasting a message to wildcard subscriptions."""
    client_id1 = await connection_manager.connect(mock_websocket, test_user)

    await connection_manager.subscribe(client_id1, "*")

    message = {"topic_data": 123}
    await connection_manager.broadcast_to_topic("any_random_topic", message)

    import json

    mock_websocket.send_text.assert_called_once_with(json.dumps(message))


async def test_websocket_disconnect_on_send_error(
    connection_manager, mock_websocket, test_user
):
    """Test that a client is disconnected if sending a message fails."""
    mock_websocket.send_text.side_effect = RuntimeError("WebSocket is not connected")

    client_id = await connection_manager.connect(mock_websocket, test_user)

    await connection_manager.send_to_client({"test": 1}, client_id)

    # Client should be removed from active connections
    assert client_id not in connection_manager.active_connections


async def test_data_provider_registration_and_unregistration(connection_manager):
    """Test registering and unregistering topic data providers."""

    def dummy_handler(topic, data):
        return {"status": "ok"}

    connection_manager.register_data_provider(
        "server-status", dummy_handler, "plugin_a"
    )
    assert connection_manager.get_data_provider("server-status") == dummy_handler

    connection_manager.unregister_data_provider("server-status")
    assert connection_manager.get_data_provider("server-status") is None


async def test_unregister_plugin_providers(connection_manager):
    """Test unregistering all data providers belonging to a specific plugin."""

    def handler1():
        pass

    def handler2():
        pass

    def handler3():
        pass

    connection_manager.register_data_provider("topic1", handler1, "plugin_a")
    connection_manager.register_data_provider("topic2", handler2, "plugin_a")
    connection_manager.register_data_provider("topic3", handler3, "plugin_b")

    connection_manager.unregister_plugin_providers("plugin_a")

    assert connection_manager.get_data_provider("topic1") is None
    assert connection_manager.get_data_provider("topic2") is None
    assert connection_manager.get_data_provider("topic3") == handler3


async def test_publish_ws_event(connection_manager, mock_websocket, test_user):
    """Test publishing custom websocket events."""
    client_id = await connection_manager.connect(mock_websocket, test_user)
    await connection_manager.subscribe(client_id, "ws_event:custom_event")

    event_data = {"key": "val"}
    await connection_manager.publish_ws_event("custom_event", event_data)

    import json

    expected = {
        "type": "ws_event",
        "event": "custom_event",
        "topic": "ws_event:custom_event",
        "data": event_data,
    }
    mock_websocket.send_text.assert_called_once_with(json.dumps(expected))


async def test_account_change_revokes_socket_before_delivery():
    from unittest.mock import AsyncMock

    from bedrock_server_manager.state.models import UserInfoState
    from bedrock_server_manager.web.schemas.users import UserResponse
    from bedrock_server_manager.web.websocket_manager import ConnectionManager

    user = UserInfoState(id=1, username="owner", role="admin")
    manager = ConnectionManager(user_provider=lambda name: user)
    socket = AsyncMock()
    client = await manager.connect(
        socket, UserResponse.model_validate(user, from_attributes=True)
    )
    await manager.subscribe(client, "*")
    user = UserInfoState(id=1, username="owner", role="user", is_active=False)
    await manager.broadcast_to_topic("private", {"data": "secret"})
    socket.send_text.assert_not_awaited()
    socket.close.assert_awaited_once()
    assert not manager.active_connections
    assert not manager.subscriptions


@pytest.mark.asyncio
async def test_websocket_close_has_deadline():
    cm = ConnectionManager()
    cm.io_timeout = 0.01
    closing = asyncio.Event()
    release = asyncio.Event()

    async def close(**kwargs):
        closing.set()
        await release.wait()

    socket = SimpleNamespace(close=close)
    user = UserResponse(
        id=1, username="test", role="admin", is_active=True, theme="default"
    )
    await cm.connect(socket, user)
    shutdown = asyncio.create_task(cm.shutdown())
    await closing.wait()
    await asyncio.wait_for(shutdown, 0.5)
    assert not cm.active_connections


@pytest.mark.asyncio
async def test_stalled_websocket_send_disconnects():
    manager = ConnectionManager()
    manager.io_timeout = 0.01

    async def send_text(data):
        await asyncio.Event().wait()

    socket = SimpleNamespace(send_text=send_text)
    user = UserResponse(
        id=1, username="test", role="admin", is_active=True, theme="default"
    )
    client_id = await manager.connect(socket, user)
    await manager.subscribe(client_id, "updates")
    await asyncio.wait_for(manager.send_to_client({"value": 1}, client_id), 0.5)
    assert client_id not in manager.active_connections
    assert "updates" not in manager.subscriptions
