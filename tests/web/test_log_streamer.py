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
        path = Path(real_bedrock_server.paths.server_log_path)
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
        assert streamer.file_positions[(topic, str(path))] == path.stat().st_size


async def test_log_streamer_delivers_truncated_file(app_context, subscribed_socket):
    path = Path(app_context.log_dir) / "bedrock_server_manager.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old data\n" * 100)
    async with subscribed_socket("app_log") as socket:
        assert await receive_log(socket, "app_log") == path.read_text()
        path.write_text("new start\n")
        assert await receive_log(socket, "app_log") == "new start\n"
        assert (
            app_context.log_streamer.file_positions[("app_log", str(path))]
            == path.stat().st_size
        )


async def test_both_application_aliases_receive_updates(app_context, subscribed_socket):
    path = Path(app_context.log_dir) / "bedrock_server_manager.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("initial\n")
    async with subscribed_socket("app_log", "app_logs") as socket:
        messages = {}
        async with asyncio.timeout(5):
            while len(messages) < 2:
                message = json.loads(await socket.recv())
                if message.get("type") == "log_update":
                    messages[message["topic"]] = message["data"]
        assert messages == {"app_log": "initial\n", "app_logs": "initial\n"}
        replacement = path.with_suffix(".replacement")
        replacement.write_text("replacement with more content\n")
        replacement.replace(path)
        messages = {}
        async with asyncio.timeout(5):
            while len(messages) < 2:
                message = json.loads(await socket.recv())
                if message.get("type") == "log_update":
                    messages[message["topic"]] = message["data"]
        assert set(messages.values()) == {"replacement with more content\n"}


@pytest.mark.parametrize("server_log", [False, True])
async def test_history_pages_reconstruct_entire_utf8_file(
    app_context, admin_auth_client, real_bedrock_server, server_log
):
    if server_log:
        path = Path(real_bedrock_server.paths.server_log_path)
        topic = f"server_log:{real_bedrock_server.server_name}"
    else:
        path = Path(app_context.log_dir) / "bedrock_server_manager.log"
        topic = "app_log"
    path.parent.mkdir(parents=True, exist_ok=True)
    original = "世界 🌍 log entry\n\n" * 12000 + "partial final line"
    path.write_text(original, encoding="utf-8")
    pages = []
    params = {"topic": topic}
    while True:
        response = await admin_auth_client.get("/api/logs/history", params=params)
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["end"] - page["start"] <= 64 * 1024
        pages.insert(0, page["data"])
        if not page["has_more"]:
            break
        params.update(before=page["start"], file_id=page["file_id"])
    assert "".join(pages) == original
    assert not app_context.log_streamer.file_positions
    replacement = path.with_suffix(".replacement")
    replacement.write_text("new file\n")
    replacement.replace(path)
    response = await admin_auth_client.get("/api/logs/history", params=params)
    assert response.status_code == 409


async def test_history_rejects_invalid_topics_and_offsets(admin_auth_client):
    assert (
        await admin_auth_client.get(
            "/api/logs/history", params={"topic": "../../secret"}
        )
    ).status_code == 400
    assert (
        await admin_auth_client.get(
            "/api/logs/history", params={"topic": "app_log", "before": -1}
        )
    ).status_code == 422


async def test_history_requires_authorization(auth_client, unauth_client):
    assert (
        await unauth_client.get("/api/logs/history", params={"topic": "app_log"})
    ).status_code == 401
    assert (
        await auth_client.get("/api/logs/history", params={"topic": "app_log"})
    ).status_code == 403


async def test_history_and_live_stream_join_without_gaps(
    app_context, subscribed_socket
):
    path = Path(app_context.log_dir) / "bedrock_server_manager.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    original = "世界 entry\n" * 2000
    path.write_text(original, encoding="utf-8")
    async with subscribed_socket("app_log") as socket:
        async with asyncio.timeout(5):
            while True:
                frame = json.loads(await socket.recv())
                if frame.get("type") == "log_update":
                    break
        history = await app_context.log_streamer.read_history(
            "app_log", frame["start"], frame["file_id"]
        )
        assert history.data + frame["data"] == original
        with path.open("ab") as output:
            output.write(b"\xf0\x9f")
        await asyncio.sleep(1.2)
        with path.open("ab") as output:
            output.write(b"\x8c\x8d\n")
        assert await receive_log(socket, "app_log") == "🌍\n"


async def test_history_cannot_read_arbitrary_server_paths(
    admin_auth_client, app_context
):
    for topic, status in (
        ("server_log:../../private", 400),
        ("server_log:missing", 404),
    ):
        response = await admin_auth_client.get(
            "/api/logs/history", params={"topic": topic}
        )
        assert response.status_code == status
    assert "missing" not in app_context._servers
