from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.plugins.api_bridge import create_app_api


@pytest.fixture
def mock_app_context():
    context = MagicMock()
    context.connection_manager = MagicMock()
    context.connection_manager.broadcast_to_topic = AsyncMock()
    context.connection_manager.send_to_user = AsyncMock()
    context.connection_manager.send_to_client = AsyncMock()
    context.connection_manager.publish_ws_event = AsyncMock()
    return context


async def test_websocket_api_bridge(mock_app_context):
    api = create_app_api("test_plugin", mock_app_context)

    # Broadcast
    res = (
        await api.websocket.websocket_broadcast(
            request={"topic": "my_topic", "data": {"key": "val"}}
        )
    ).model_dump(mode="python")
    assert res["status"] == "success"
    mock_app_context.connection_manager.broadcast_to_topic.assert_called_once_with(
        "my_topic", {"type": "broadcast", "topic": "my_topic", "data": {"key": "val"}}
    )

    # Send to user
    res = (
        await api.websocket.websocket_send_to_user(
            request={"username": "admin", "data": {"msg": "hi"}}
        )
    ).model_dump(mode="python")
    assert res["status"] == "success"
    mock_app_context.connection_manager.send_to_user.assert_called_once_with(
        "admin", {"msg": "hi"}
    )

    # Send to client
    res = (
        await api.websocket.websocket_send_to_client(
            request={"client_id": "client123", "data": {"msg": "direct"}}
        )
    ).model_dump(mode="python")
    assert res["status"] == "success"
    mock_app_context.connection_manager.send_to_client.assert_called_once_with(
        {"msg": "direct"}, "client123"
    )

    # Register data provider
    def my_handler(data):
        return "ok"

    res = await api.runtime.register_data_provider("my_data", my_handler)
    assert res is None
    mock_app_context.connection_manager.register_data_provider.assert_called_once_with(
        topic="my_data", handler=my_handler, plugin_name="test_plugin"
    )

    # Unregister data provider
    res = (
        await api.websocket.websocket_unregister_data_provider(
            request={"topic": "my_data"}
        )
    ).model_dump(mode="python")
    assert res["status"] == "success"
    mock_app_context.connection_manager.unregister_data_provider.assert_called_once_with(
        "my_data"
    )

    # Publish ws event
    res = (
        await api.websocket.websocket_publish_ws_event(
            request={"event_name": "custom_evt", "data": {"foo": "bar"}}
        )
    ).model_dump(mode="python")
    assert res["status"] == "success"
    mock_app_context.connection_manager.publish_ws_event.assert_called_once_with(
        "custom_evt", {"foo": "bar"}
    )

    # Test list_available_apis works without error
    available = api.list_available_apis()
    assert isinstance(available, list)
    websocket_apis = [a for a in available if a["domain"] == "websocket"]
    assert len(websocket_apis) > 0
