import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.web.log_streamer import LogStreamer


@pytest.fixture
def log_streamer(app_context):
    return LogStreamer(app_context)


@pytest.mark.asyncio
async def test_log_streamer_start_stop(log_streamer):
    """Test start and stop lifecycle methods for LogStreamer."""
    assert not log_streamer.running
    assert log_streamer._task is None

    log_streamer.start()
    assert log_streamer.running
    assert log_streamer._task is not None
    assert not log_streamer._task.done()

    # Starting again should be a no-op
    task_ref = log_streamer._task
    log_streamer.start()
    assert log_streamer._task is task_ref

    log_streamer.stop()
    assert not log_streamer.running
    assert log_streamer._task is None


@pytest.mark.asyncio
async def test_log_streamer_reads_app_log(log_streamer, app_context, tmp_path):
    """Test that the log streamer reads and broadcasts app_log."""
    # Setup mock file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    app_context.settings.set("paths.logs", str(log_dir))
    log_file = log_dir / "bedrock_server_manager.log"
    log_file.write_text("initial log\n")

    # Setup mock connections manager with a subscription
    mock_broadcast = AsyncMock()
    app_context.connection_manager.subscriptions = {"app_log": {"client1"}}
    app_context.connection_manager.broadcast_to_topic = mock_broadcast

    # Run one iteration of the stream
    log_streamer.running = True
    task = asyncio.create_task(log_streamer._stream_logs())
    await asyncio.sleep(0.1)  # First run sets up file position

    # Write new data explicitly defining newline characters
    with open(log_file, "ab") as f:
        f.write(b"new log line\n")

    await asyncio.sleep(1.2)  # Wait for next tick (sleep is 1.0s)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check broadcast was called with correct data
    mock_broadcast.assert_called_with(
        "app_log", {"type": "log_update", "topic": "app_log", "data": "new log line\n"}
    )


@pytest.mark.asyncio
async def test_log_streamer_reads_server_log(
    log_streamer, app_context, tmp_path, monkeypatch
):
    """Test that the log streamer reads and broadcasts server logs."""
    # Setup mock server and log file
    server_dir = tmp_path / "servers" / "test_server"
    server_dir.mkdir(parents=True)
    log_file = server_dir / "server.log"
    log_file.write_text("server start\n")

    mock_server = MagicMock()
    mock_server.server_log_path = str(log_file)
    monkeypatch.setattr(app_context, "get_server", MagicMock(return_value=mock_server))

    mock_broadcast = AsyncMock()
    app_context.connection_manager.subscriptions = {
        "server_log:test_server": {"client1"}
    }
    app_context.connection_manager.broadcast_to_topic = mock_broadcast

    # Run
    log_streamer.running = True
    task = asyncio.create_task(log_streamer._stream_logs())
    await asyncio.sleep(0.1)

    with open(log_file, "ab") as f:
        f.write(b"player joined\n")

    await asyncio.sleep(1.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    mock_broadcast.assert_called_with(
        "server_log:test_server",
        {
            "type": "log_update",
            "topic": "server_log:test_server",
            "data": "player joined\n",
        },
    )


@pytest.mark.asyncio
async def test_log_streamer_file_rotation(log_streamer, app_context, tmp_path):
    """Test log streamer handles file rotation (file getting smaller)."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    app_context.settings.set("paths.logs", str(log_dir))
    log_file = log_dir / "bedrock_server_manager.log"
    # Use binary write to ensure explicit length
    log_file.write_bytes(b"old data\n" * 100)  # Big file

    mock_broadcast = AsyncMock()
    app_context.connection_manager.subscriptions = {"app_log": {"client1"}}
    app_context.connection_manager.broadcast_to_topic = mock_broadcast

    log_streamer.running = True
    task = asyncio.create_task(log_streamer._stream_logs())
    await asyncio.sleep(0.1)  # Reads initial position

    assert log_streamer.file_positions[str(log_file)] > 0

    # Simulate file rotation / truncate
    log_file.write_bytes(b"new start\n")
    expected_length = len(b"new start\n")

    await asyncio.sleep(1.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Broadcast should have sent the new data because position was reset to 0
    mock_broadcast.assert_called_with(
        "app_log", {"type": "log_update", "topic": "app_log", "data": "new start\n"}
    )
    assert log_streamer.file_positions[str(log_file)] == expected_length
