import pytest
from unittest.mock import MagicMock, patch

from bedrock_server_manager.plugins.event_trigger import trigger_plugin_event


@pytest.fixture
def mock_plugin_manager():
    with patch(
        "bedrock_server_manager.plugins.event_trigger.get_plugin_manager_instance"
    ) as mock_get:
        mock_manager = MagicMock()
        mock_get.return_value = mock_manager
        yield mock_manager


def test_trigger_plugin_event_sync(mock_plugin_manager):
    @trigger_plugin_event(before="before_sync", after="after_sync")
    def my_sync_func(a, b=10):
        return a + b

    result = my_sync_func(5)

    assert result == 15
    mock_plugin_manager.trigger_event.assert_any_call("before_sync", a=5, b=10)
    mock_plugin_manager.trigger_event.assert_any_call(
        "after_sync", a=5, b=10, result=15
    )


@pytest.mark.asyncio
async def test_trigger_plugin_event_async(mock_plugin_manager):
    @trigger_plugin_event(before="before_async", after="after_async")
    async def my_async_func(a, b=20):
        return a + b

    result = await my_async_func(10)

    assert result == 30
    mock_plugin_manager.trigger_event.assert_any_call("before_async", a=10, b=20)
    mock_plugin_manager.trigger_event.assert_any_call(
        "after_async", a=10, b=20, result=30
    )


def test_trigger_plugin_event_no_args(mock_plugin_manager):
    @trigger_plugin_event
    def my_func():
        return "done"

    my_func()
    mock_plugin_manager.trigger_event.assert_not_called()


def test_trigger_plugin_event_only_before(mock_plugin_manager):
    @trigger_plugin_event(before="only_before")
    def my_func():
        pass

    my_func()
    mock_plugin_manager.trigger_event.assert_called_once_with("only_before")


def test_trigger_plugin_event_only_after(mock_plugin_manager):
    @trigger_plugin_event(after="only_after")
    def my_func():
        return "finished"

    my_func()
    mock_plugin_manager.trigger_event.assert_called_once_with(
        "only_after", result="finished"
    )
