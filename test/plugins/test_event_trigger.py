import pytest
from unittest.mock import MagicMock

from bedrock_server_manager.plugins.event_trigger import trigger_plugin_event


@pytest.fixture
def app_context():
    mock_context = MagicMock()
    mock_context.plugin_manager = MagicMock()
    return mock_context


def test_trigger_plugin_event_sync(app_context):
    @trigger_plugin_event(before="before_sync", after="after_sync")
    def my_sync_func(app_context, a, b=10):
        return a + b

    result = my_sync_func(app_context, 5)

    assert result == 15
    app_context.plugin_manager.trigger_event.assert_any_call(
        "before_sync", app_context=app_context, a=5, b=10
    )
    app_context.plugin_manager.trigger_event.assert_any_call(
        "after_sync", app_context=app_context, a=5, b=10, result=15
    )


@pytest.mark.asyncio
async def test_trigger_plugin_event_async(app_context):
    @trigger_plugin_event(before="before_async", after="after_async")
    async def my_async_func(app_context, a, b=20):
        return a + b

    result = await my_async_func(app_context, 10)

    assert result == 30
    app_context.plugin_manager.trigger_event.assert_any_call(
        "before_async", app_context=app_context, a=10, b=20
    )
    app_context.plugin_manager.trigger_event.assert_any_call(
        "after_async", app_context=app_context, a=10, b=20, result=30
    )


def test_trigger_plugin_event_no_args(app_context):
    @trigger_plugin_event
    def my_func(app_context):
        return "done"

    my_func(app_context)
    app_context.plugin_manager.trigger_event.assert_not_called()


def test_trigger_plugin_event_only_before(app_context):
    @trigger_plugin_event(before="only_before")
    def my_func(app_context):
        pass

    my_func(app_context)
    app_context.plugin_manager.trigger_event.assert_called_once_with(
        "only_before", app_context=app_context
    )


def test_trigger_plugin_event_only_after(app_context):
    @trigger_plugin_event(after="only_after")
    def my_func(app_context):
        return "finished"

    my_func(app_context)
    app_context.plugin_manager.trigger_event.assert_called_once_with(
        "only_after", app_context=app_context, result="finished"
    )
