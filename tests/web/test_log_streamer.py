import asyncio
import json
from pathlib import Path

import pytest


async def receive_log(socket, topic):
    async with asyncio.timeout(5):
        while True:
            message = json.loads(await socket.recv())
            if message.get("type") == "log_update" and message.get("topic") == topic:
                return message["data"]


async def test_log_streamer_start_stop(app_context):
    streamer = app_context.log_streamer
    assert not streamer.running
    streamer.start()
    task = streamer._task
    streamer.start()
    assert streamer._task is task
    await streamer.shutdown()
    assert task.done()
    assert not streamer.running
    assert streamer._task is None


@pytest.mark.parametrize("server_log", [False, True])
async def test_log_streamer_delivers_real_file_updates(
    app_context, real_bedrock_server, subscribed_socket, server_log
):
    streamer = app_context.log_streamer
    if server_log:
        topic = f"server_log:{real_bedrock_server.server_name}"
        path = Path(real_bedrock_server.server_log_path)
    else:
        topic = "app_log"
        path = Path(app_context.log_dir) / "bedrock_server_manager.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("initial line\n")
    async with subscribed_socket(topic) as socket:
        assert await receive_log(socket, topic) == "initial line\n"
        with path.open("a") as output:
            output.write("appended line\n")
        assert await receive_log(socket, topic) == "appended line\n"
        assert streamer.file_positions[str(path)] == path.stat().st_size


async def test_log_streamer_delivers_truncated_file(app_context, subscribed_socket):
    path = Path(app_context.log_dir) / "bedrock_server_manager.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old data\n" * 100)
    async with subscribed_socket("app_log") as socket:
        assert await receive_log(socket, "app_log") == path.read_text()
        path.write_text("new start\n")
        assert await receive_log(socket, "app_log") == "new start\n"
        assert app_context.log_streamer.file_positions[str(path)] == path.stat().st_size
