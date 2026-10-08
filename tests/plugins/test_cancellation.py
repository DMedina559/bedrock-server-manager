import pytest

from bedrock_server_manager.plugins.event_trigger import trigger_event


@pytest.mark.parametrize("async_handler", [False, True])
async def test_loaded_plugin_cancels_before_target(
    app_context, plugin_factory, async_handler
):
    handler = "async def" if async_handler else "def"
    plugin = await plugin_factory(
        "cancel_event",
        f"""
from bedrock_server_manager.plugins import PluginBase, app_event
class Canceller(PluginBase):
    version = "1.0.0"
    def on_load(self):
        self.after_called = False
    @app_event("before_event")
    {handler} cancel(self, event, **kwargs):
        event.cancel("Cancelled by plugin")
    @app_event("after_event")
    async def after(self, **kwargs):
        self.after_called = True
""",
    )
    executed = False

    @trigger_event(before="before_event", after="after_event")
    async def target(app_context):
        nonlocal executed
        executed = True
        return {"status": "success"}

    assert await target(app_context) == {
        "status": "canceled",
        "message": "Cancelled by plugin",
    }
    assert not executed
    assert not plugin.after_called
