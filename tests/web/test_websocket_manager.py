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


async def test_real_socket_connect_disconnect(app_context, subscribed_socket):
    manager = app_context.connection_manager
    async with subscribed_socket("topicA", "topicB"):
        assert len(manager.active_connections) == 1
        client_id = next(iter(manager.active_connections))
        assert set(manager.subscriptions["topicA"]) == {client_id}
        assert set(manager.subscriptions["topicB"]) == {client_id}
    async with asyncio.timeout(5):
        while manager.active_connections:
            await asyncio.sleep(0.01)
    assert not manager.subscriptions


async def test_direct_and_user_delivery_to_real_sockets(
    app_context, subscribed_socket, test_admin_user
):
    import json

    manager = app_context.connection_manager
    async with subscribed_socket() as first, subscribed_socket() as second:
        clients = list(manager.active_connections)
        await manager.send_to_client({"direct": True}, clients[0])
        async with asyncio.timeout(5):
            assert json.loads(await first.recv()) == {"direct": True}
        await manager.send_to_user(test_admin_user.username, {"alert": "update"})
        async with asyncio.timeout(5):
            assert json.loads(await first.recv()) == {"alert": "update"}
            assert json.loads(await second.recv()) == {"alert": "update"}


@pytest.mark.parametrize("subscription", ["my_topic", "*"])
async def test_topic_broadcast_reaches_only_real_subscribers(
    app_context, subscribed_socket, subscription
):
    import json

    manager = app_context.connection_manager
    async with (
        subscribed_socket(subscription) as subscribed,
        subscribed_socket() as other,
    ):
        await manager.broadcast_to_topic("my_topic", {"topic_data": 123})
        clients = list(manager.active_connections)
        await manager.send_to_client({"sentinel": True}, clients[-1])
        async with asyncio.timeout(5):
            assert json.loads(await subscribed.recv()) == {"topic_data": 123}
            assert json.loads(await other.recv()) == {"sentinel": True}


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


async def test_publish_ws_event(app_context, subscribed_socket):
    import json

    async with subscribed_socket("ws_event:custom_event") as socket:
        await app_context.connection_manager.publish_ws_event(
            "custom_event", {"key": "val"}
        )
        async with asyncio.timeout(5):
            assert json.loads(await socket.recv()) == {
                "type": "ws_event",
                "event": "custom_event",
                "topic": "ws_event:custom_event",
                "data": {"key": "val"},
            }


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
