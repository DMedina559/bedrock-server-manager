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
