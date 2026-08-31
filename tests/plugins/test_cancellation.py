from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.plugins.event_trigger import trigger_event


def test_cancellable_event_sync(monkeypatch):
    mock_context = MagicMock()
    mock_context.plugin_manager = MagicMock()
    # Mock broadcast_event to avoid unawaited coroutines
    mock_context.connection_manager = MagicMock()

    import bedrock_server_manager.plugins.event_trigger as et

    mock_broadcast = MagicMock()
    monkeypatch.setattr(et, "broadcast_event", mock_broadcast, raising=False)

    def mock_trigger_event(event_name, *args, **kwargs):
        if event_name == "before_event":
            kwargs["event"].cancel("Sync cancelled")

    mock_context.plugin_manager.trigger_event.side_effect = mock_trigger_event

    @trigger_event(before="before_event")
    def sync_target(app_context):
        return {"status": "success", "message": "should not reach"}

    result = sync_target(app_context=mock_context)
    assert result == {"status": "canceled", "message": "Sync cancelled"}


@pytest.mark.asyncio
async def test_cancellable_event_async(monkeypatch):
    from unittest.mock import AsyncMock

    mock_context = MagicMock()
    mock_context.plugin_manager = MagicMock()
    mock_context.plugin_manager.trigger_event_async = AsyncMock()
    mock_context.connection_manager = AsyncMock()

    import bedrock_server_manager.plugins.event_trigger as et

    mock_broadcast = AsyncMock()
    monkeypatch.setattr(et, "async_broadcast_event", mock_broadcast, raising=False)

    async def mock_trigger_event_async(event_name, *args, **kwargs):
        if event_name == "before_event":
            kwargs["event"].cancel("Async cancelled")

    mock_context.plugin_manager.trigger_event_async.side_effect = (
        mock_trigger_event_async
    )

    @trigger_event(before="before_event")
    async def async_target(app_context):
        return {"status": "success", "message": "should not reach"}

    result = await async_target(app_context=mock_context)
    assert result == {"status": "canceled", "message": "Async cancelled"}
