from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.plugins.event_trigger import trigger_app_event


@pytest.fixture
def mock_app_context():
    mock_context = MagicMock()
    mock_context.plugin_manager = MagicMock()
    mock_context.plugin_manager.trigger_event_async = AsyncMock()
    mock_context.connection_manager = AsyncMock()

    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    mock_context.loop = mock_loop
    return mock_context


def test_trigger_app_event_sync_hooks(mock_app_context):
    """Test trigger_app_event wraps a synchronous function, triggering both before and after hooks."""

    @trigger_app_event(before="sync_before", after="sync_after")
    def sync_target(app_context, multiplier, increment=5):
        return multiplier * increment

    result = sync_target(mock_app_context, 10)
    assert result == 50

    mock_app_context.plugin_manager.trigger_event.assert_any_call(
        "sync_before", app_context=mock_app_context, multiplier=10, increment=5
    )
    mock_app_context.plugin_manager.trigger_event.assert_any_call(
        "sync_after",
        app_context=mock_app_context,
        multiplier=10,
        increment=5,
        result=50,
    )

    mock_app_context.connection_manager.broadcast_to_topic.assert_any_call(
        "event:sync_before",
        {
            "type": "event",
            "topic": "event:sync_before",
            "data": {"multiplier": 10, "increment": 5},
        },
    )
    mock_app_context.connection_manager.broadcast_to_topic.assert_any_call(
        "event:sync_after",
        {
            "type": "event",
            "topic": "event:sync_after",
            "data": {"multiplier": 10, "increment": 5, "result": 50},
        },
    )


@pytest.mark.asyncio
async def test_trigger_app_event_async_hooks(mock_app_context, monkeypatch):
    """Test trigger_app_event successfully wraps async coroutines awaiting correctly."""

    mock_broadcast = MagicMock()

    async def mock_async_broadcast(*args, **kwargs):
        pass

    import bedrock_server_manager.plugins.event_trigger as et

    monkeypatch.setattr(et, "broadcast_event", mock_broadcast, raising=False)
    monkeypatch.setattr(
        et, "async_broadcast_event", mock_async_broadcast, raising=False
    )

    @et.trigger_app_event(before="async_before", after="async_after")
    async def async_target(app_context, val):
        import asyncio

        await asyncio.sleep(0)
        return val + 10

    # Ensure trigger_event_async is properly mocked if it exists
    if hasattr(mock_app_context.plugin_manager, "trigger_event_async"):
        from unittest.mock import AsyncMock

        mock_app_context.plugin_manager.trigger_event_async = AsyncMock()

    result = await async_target(app_context=mock_app_context, val=20)
    assert result == 30

    if hasattr(mock_app_context.plugin_manager, "trigger_event_async"):
        mock_app_context.plugin_manager.trigger_event_async.assert_any_call(
            "async_before", app_context=mock_app_context, val=20
        )
        mock_app_context.plugin_manager.trigger_event_async.assert_any_call(
            "async_after", app_context=mock_app_context, val=20, result=30
        )
    else:
        mock_app_context.plugin_manager.trigger_event.assert_any_call(
            "async_before", app_context=mock_app_context, val=20
        )
        mock_app_context.plugin_manager.trigger_event.assert_any_call(
            "async_after", app_context=mock_app_context, val=20, result=30
        )


def test_trigger_app_event_no_args(mock_app_context):
    """Test trigger_app_event skips triggering when no string events are mapped to kwargs."""

    @trigger_app_event
    def blank_target(app_context):
        return "blank"

    assert blank_target(mock_app_context) == "blank"
    mock_app_context.plugin_manager.trigger_event.assert_not_called()
    mock_app_context.connection_manager.broadcast_to_topic.assert_not_called()


def test_trigger_app_event_only_before(mock_app_context):
    """Test trigger_app_event only executes the before hook if no after is given."""

    @trigger_app_event(before="only_before")
    def my_target(app_context):
        return True

    my_target(mock_app_context)
    mock_app_context.plugin_manager.trigger_event.assert_called_once_with(
        "only_before", app_context=mock_app_context
    )


def test_trigger_app_event_only_after(mock_app_context):
    """Test trigger_app_event only executes the after hook if no before is given."""

    @trigger_app_event(after="only_after")
    def my_target(app_context):
        return "success_val"

    my_target(mock_app_context)
    mock_app_context.plugin_manager.trigger_event.assert_called_once_with(
        "only_after", app_context=mock_app_context, result="success_val"
    )
