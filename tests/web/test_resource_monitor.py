import asyncio
import json


async def test_resource_monitor_start_stop(app_context):
    monitor = app_context.resource_monitor
    assert monitor._task is None
    monitor.start()
    task = monitor._task
    monitor.start()
    assert monitor._task is task
    await monitor.shutdown()
    assert task.done()
    assert monitor._task is None


async def test_resource_monitor_broadcasts_actual_server_status(
    app_context, real_bedrock_server, subscribed_socket
):
    topic = f"resource-monitor:{real_bedrock_server.server_name}"
    async with subscribed_socket(topic) as socket:
        async with asyncio.timeout(5):
            message = json.loads(await socket.recv())
        assert message == {
            "type": "resource_update",
            "topic": topic,
            "data": {"status": "success", "process_info": None},
        }
        assert not await real_bedrock_server.is_running()


async def test_resource_monitor_recovers_after_provider_failure(
    app_context, real_bedrock_server, subscribed_socket, monkeypatch, caplog
):
    topic = f"resource-monitor:{real_bedrock_server.server_name}"
    monitor = app_context.resource_monitor

    def unavailable(name):
        raise RuntimeError("Injected provider failure")

    async with subscribed_socket(topic) as socket:
        with monkeypatch.context() as fault:
            fault.setattr(monitor, "server_provider", unavailable)
            async with asyncio.timeout(5):
                while "Injected provider failure" not in caplog.text:
                    await asyncio.sleep(0.01)
            assert not monitor._task.done()
        async with asyncio.timeout(5):
            message = json.loads(await socket.recv())
        assert message["topic"] == topic
        assert message["data"] == {"status": "success", "process_info": None}


async def test_resource_monitor_broadcasts_live_process_then_stopped_state(
    app_context, real_bedrock_server, subscribed_socket
):
    server = real_bedrock_server
    await server.start()
    child = server._process
    topic = f"resource-monitor:{server.server_name}"
    async with subscribed_socket(topic) as socket:
        async with asyncio.timeout(10):
            message = json.loads(await socket.recv())
        info = message["data"]["process_info"]
        assert message["topic"] == topic
        assert info["pid"] == child.pid
        assert info["memory_mb"] > 0
        assert info["cpu_percent"] >= 0
        assert info["uptime"]
        await server.stop()
        async with asyncio.timeout(10):
            while True:
                message = json.loads(await socket.recv())
                if message["data"]["process_info"] is None:
                    break
        assert child.returncode is not None
        assert not await server.is_running()
