import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from bedrock_server_manager.plugins.event_trigger import trigger_plugin_event


@pytest.fixture
def app_context():
    """Provides a mocked AppContext for testing the event trigger."""
    mock_context = MagicMock()
    mock_context.plugin_manager = MagicMock()
    # Mock the connection manager and its async broadcast method
    mock_context.connection_manager = AsyncMock()
    # Provide a mock loop that reports it is running
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    mock_context.loop = mock_loop
    return mock_context


def test_trigger_plugin_event_sync(app_context):
    @trigger_plugin_event(before="before_sync", after="after_sync")
    def my_sync_func(app_context, a, b=10):
        return a + b

    result = my_sync_func(app_context, 5)

    assert result == 15
    # Check that the original plugin event was triggered
    app_context.plugin_manager.trigger_event.assert_any_call(
        "before_sync", app_context=app_context, a=5, b=10
    )
    app_context.plugin_manager.trigger_event.assert_any_call(
        "after_sync", app_context=app_context, a=5, b=10, result=15
    )
    # Check that the WebSocket broadcast was called
    app_context.connection_manager.broadcast_to_topic.assert_any_call(
        "event:before_sync",
        {
            "type": "event",
            "topic": "event:before_sync",
            "data": {"a": 5, "b": 10},
        },
    )
    app_context.connection_manager.broadcast_to_topic.assert_any_call(
        "event:after_sync",
        {
            "type": "event",
            "topic": "event:after_sync",
            "data": {"a": 5, "b": 10, "result": 15},
        },
    )


@pytest.mark.asyncio
async def test_trigger_plugin_event_async(app_context):
    @trigger_plugin_event(before="before_async", after="after_async")
    async def my_async_func(app_context, a, b=20):
        await asyncio.sleep(0)  # Simulate async operation
        return a + b

    result = await my_async_func(app_context, 10)

    assert result == 30
    app_context.plugin_manager.trigger_event.assert_any_call(
        "before_async", app_context=app_context, a=10, b=20
    )
    app_context.plugin_manager.trigger_event.assert_any_call(
        "after_async", app_context=app_context, a=10, b=20, result=30
    )
    # Check that the WebSocket broadcast was awaited
    app_context.connection_manager.broadcast_to_topic.assert_any_await(
        "event:before_async",
        {
            "type": "event",
            "topic": "event:before_async",
            "data": {"a": 10, "b": 20},
        },
    )
    app_context.connection_manager.broadcast_to_topic.assert_any_await(
        "event:after_async",
        {
            "type": "event",
            "topic": "event:after_async",
            "data": {"a": 10, "b": 20, "result": 30},
        },
    )


def test_trigger_plugin_event_no_args(app_context):
    @trigger_plugin_event
    def my_func(app_context):
        return "done"

    my_func(app_context)
    app_context.plugin_manager.trigger_event.assert_not_called()
    app_context.connection_manager.broadcast_to_topic.assert_not_called()


def test_trigger_plugin_event_only_before(app_context):
    @trigger_plugin_event(before="only_before")
    def my_func(app_context):
        pass

    my_func(app_context)
    app_context.plugin_manager.trigger_event.assert_called_once_with(
        "only_before", app_context=app_context
    )
    app_context.connection_manager.broadcast_to_topic.assert_called_once()


def test_trigger_plugin_event_only_after(app_context):
    @trigger_plugin_event(after="only_after")
    def my_func(app_context):
        return "finished"

    my_func(app_context)
    app_context.plugin_manager.trigger_event.assert_called_once_with(
        "only_after", app_context=app_context, result="finished"
    )
    app_context.connection_manager.broadcast_to_topic.assert_called_once()
