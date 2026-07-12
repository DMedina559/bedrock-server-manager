import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.web.resource_monitor import ResourceMonitor


@pytest.fixture
def resource_monitor(app_context):
    return ResourceMonitor(app_context)


@pytest.mark.asyncio
async def test_resource_monitor_start_stop(resource_monitor):
    """Test start and stop lifecycle methods for ResourceMonitor."""
    assert resource_monitor._task is None

    resource_monitor.start()
    assert resource_monitor._task is not None
    assert not resource_monitor._task.done()

    resource_monitor.stop()
    assert resource_monitor._task is None


@pytest.mark.asyncio
async def test_resource_monitor_loop_broadcasts(
    resource_monitor, app_context, monkeypatch
):
    """Test that the monitor loop broadcasts data for subscribed topics."""
    # Setup mock connections manager with a subscription
    mock_broadcast = AsyncMock()
    app_context.connection_manager.subscriptions = {
        "resource-monitor:test_server": {"client1"}
    }
    app_context.connection_manager.broadcast_to_topic = mock_broadcast

    # Mock system API call
    mock_info = {"cpu": 10, "mem": 50}
    monkeypatch.setattr(
        "bedrock_server_manager.api.system.get_bedrock_process_info",
        MagicMock(return_value=mock_info),
    )

    # We want to run the loop manually for one iteration, so we mock sleep to raise an exception to break the loop
    # or just call the loop in a task and cancel it

    task = asyncio.create_task(resource_monitor._monitor_loop())
    await asyncio.sleep(0.1)  # Let it run
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check broadcast was called with correct data
    mock_broadcast.assert_called_with(
        "resource-monitor:test_server",
        {
            "type": "resource_update",
            "topic": "resource-monitor:test_server",
            "data": mock_info,
        },
    )


@pytest.mark.asyncio
async def test_resource_monitor_loop_no_subscribers(
    resource_monitor, app_context, monkeypatch
):
    """Test that the monitor loop skips topics without subscribers."""
    mock_broadcast = AsyncMock()
    app_context.connection_manager.subscriptions = {
        "resource-monitor:test_server": set()
    }  # Empty set
    app_context.connection_manager.broadcast_to_topic = mock_broadcast

    monkeypatch.setattr(
        "bedrock_server_manager.api.system.get_bedrock_process_info", MagicMock()
    )

    task = asyncio.create_task(resource_monitor._monitor_loop())
    await asyncio.sleep(0.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should not have broadcasted
    mock_broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_resource_monitor_exception_handling(
    resource_monitor, app_context, monkeypatch
):
    """Test that the monitor loop survives exceptions and continues running."""
    # Make it throw an exception on first broadcast
    mock_broadcast = AsyncMock(side_effect=Exception("Test Exception"))
    app_context.connection_manager.subscriptions = {
        "resource-monitor:test_server": {"client1"}
    }
    app_context.connection_manager.broadcast_to_topic = mock_broadcast

    monkeypatch.setattr(
        "bedrock_server_manager.api.system.get_bedrock_process_info",
        MagicMock(return_value={}),
    )

    task = asyncio.create_task(resource_monitor._monitor_loop())
    await asyncio.sleep(0.1)

    # The task should still be running and not done (survived exception)
    assert not task.done()

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
