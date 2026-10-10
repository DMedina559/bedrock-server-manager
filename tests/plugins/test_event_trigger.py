import pytest

from bedrock_server_manager.plugins.event_trigger import trigger_event


@pytest.mark.parametrize(
    "before,after",
    [("before", "after"), ("before", None), (None, "after"), (None, None)],
)
async def test_event_hooks_dispatch_to_loaded_plugin(
    app_context, plugin_factory, before, after
):
    plugin = await plugin_factory(
        "event_recorder",
        """
from bedrock_server_manager.plugins import PluginBase, app_event
class Recorder(PluginBase):
    version = "1.0.0"
    def on_load(self):
        self.received = []
    @app_event("before")
    async def before(self, **kwargs):
        self.received.append(("before", kwargs))
    @app_event("after")
    async def after(self, **kwargs):
        self.received.append(("after", kwargs))
""",
    )

    @trigger_event(before=before, after=after)
    async def target(app_context, multiplier, increment=5):
        plugin.received.append(("target", {}))
        return multiplier * increment

    assert await target(app_context, 10) == 50
    expected = (
        (["before"] if before else []) + ["target"] + (["after"] if after else [])
    )
    assert [name for name, _ in plugin.received] == expected
    for name, payload in plugin.received:
        if name == "target":
            continue
        assert payload["multiplier"] == 10
        assert payload["increment"] == 5
        assert "app_context" not in payload
        assert not payload["event"].is_cancelled
        if name == "after":
            assert payload["result"] == 50
    if before and after:
        assert plugin.received[0][1]["event"] is plugin.received[-1][1]["event"]


async def test_event_hooks_publish_safe_payloads_to_real_socket(
    app_context, subscribed_socket
):
    import asyncio
    import json

    @trigger_event(before="socket_before", after="socket_after")
    async def target(app_context, value):
        return value * 2

    async with subscribed_socket("event:socket_before", "event:socket_after") as socket:
        assert await target(app_context, 4) == 8
        async with asyncio.timeout(5):
            before = json.loads(await socket.recv())
            after = json.loads(await socket.recv())
        assert before == {
            "type": "event",
            "topic": "event:socket_before",
            "epoch": before["epoch"],
            "revision": before["revision"],
            "data": {"value": 4},
        }
        assert after == {
            "type": "event",
            "topic": "event:socket_after",
            "epoch": after["epoch"],
            "revision": after["revision"],
            "data": {"value": 4, "result": 8},
        }

        assert before["epoch"] == after["epoch"]
        assert after["revision"] > before["revision"]


async def test_delayed_plugin_callback_preserves_original_event_version(
    app_context, subscribed_socket, monkeypatch
):
    import asyncio
    import json

    from bedrock_server_manager.state_version import state_clock

    entered = asyncio.Event()
    release = asyncio.Event()
    original = app_context.plugin_manager.trigger_event

    async def delayed(event_name, **kwargs):
        if event_name == "delayed_after":
            entered.set()
            await release.wait()
        await original(event_name, **kwargs)

    monkeypatch.setattr(app_context.plugin_manager, "trigger_event", delayed)

    @trigger_event(after="delayed_after")
    async def target(app_context):
        return "captured"

    async with subscribed_socket("event:delayed_after") as socket:
        pending = asyncio.create_task(target(app_context))
        try:
            async with asyncio.timeout(5):
                await entered.wait()
            newer = state_clock.capture()
            release.set()
            await pending
            async with asyncio.timeout(5):
                message = json.loads(await socket.recv())
            assert message["epoch"] == newer["epoch"]
            assert message["revision"] < newer["revision"]
        finally:
            release.set()
            await asyncio.gather(pending, return_exceptions=True)
