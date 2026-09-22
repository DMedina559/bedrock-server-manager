from unittest.mock import MagicMock

from bedrock_server_manager.plugins.event_trigger import trigger_event


async def test_cancellable_event_sync(monkeypatch):
    from unittest.mock import AsyncMock

    mock_context = MagicMock()
    mock_context.plugin_manager = MagicMock()
    mock_context.plugin_manager.trigger_event = AsyncMock()
    mock_context.connection_manager = AsyncMock()

    import bedrock_server_manager.plugins.event_trigger as et

    mock_broadcast = AsyncMock()
    monkeypatch.setattr(et, "async_broadcast_event", mock_broadcast, raising=False)

    async def mock_trigger_event(event_name, *args, **kwargs):
        if event_name == "before_event":
            kwargs["event"].cancel("Sync cancelled")

    mock_context.plugin_manager.trigger_event.side_effect = mock_trigger_event

    @trigger_event(before="before_event")
    async def sync_target(app_context):
        return {"status": "success", "message": "should not reach"}

    result = await sync_target(app_context=mock_context)
    assert result == {"status": "canceled", "message": "Sync cancelled"}


async def test_cancellable_event_async(monkeypatch):
    from unittest.mock import AsyncMock

    mock_context = MagicMock()
    mock_context.plugin_manager = MagicMock()
    mock_context.plugin_manager.trigger_event = AsyncMock()
    mock_context.connection_manager = AsyncMock()

    import bedrock_server_manager.plugins.event_trigger as et

    mock_broadcast = AsyncMock()
    monkeypatch.setattr(et, "async_broadcast_event", mock_broadcast, raising=False)

    async def mock_trigger_event(event_name, *args, **kwargs):
        if event_name == "before_event":
            kwargs["event"].cancel("Async cancelled")

    mock_context.plugin_manager.trigger_event.side_effect = mock_trigger_event

    @trigger_event(before="before_event")
    async def async_target(app_context):
        return {"status": "success", "message": "should not reach"}

    result = await async_target(app_context=mock_context)
    assert result == {"status": "canceled", "message": "Async cancelled"}
