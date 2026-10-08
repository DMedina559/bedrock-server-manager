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
            "data": {"value": 4},
        }
        assert after == {
            "type": "event",
            "topic": "event:socket_after",
            "data": {"value": 4, "result": 8},
        }
