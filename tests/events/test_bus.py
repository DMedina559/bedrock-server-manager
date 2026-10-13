"""Independent delivery semantics and application-owned event integrations."""

import asyncio

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from bedrock_server_manager.events import (
    CancellableEvent,
    EventBus,
    EventDefinition,
    EventOptions,
)
from bedrock_server_manager.events.bus import correlation_scope


async def test_standalone_delivery_isolated_payloads_and_bounded_history():
    bus = EventBus(EventOptions(history_limit=2))
    received = []

    async def mutate(**data):
        data["items"].append("changed")

    async def record(**data):
        received.append(data)

    bus.subscribe("demo", mutate, owner="first")
    bus.subscribe("*", record, owner="second")
    bus.subscribe("demo", record, owner="second")
    payload = {"items": ["original"]}
    for _ in range(3):
        result = await bus.emit("demo", payload)
        assert result.listeners_called == 2
        assert result.duration_ms > 0
    assert payload == {"items": ["original"]}
    assert received == [{"items": ["original"]}] * 3
    snapshot = bus.diagnostics()
    assert len(snapshot.recent) == 2 and snapshot.emitted == 3
    assert "data" not in snapshot.model_dump()["recent"][0]
    snapshot.recent.clear()
    assert len(bus.diagnostics().recent) == 2
    await bus.close()
    with pytest.raises(RuntimeError):
        await bus.emit("demo")


async def test_recursion_is_scoped_by_identity_and_bus():
    first, second = EventBus(), EventBus()
    first.registry.register(
        EventDefinition(name="demo", identity_keys=("server_name",))
    )
    nested = []

    async def listener(server_name):
        nested.append(await first.emit("demo", {"server_name": server_name}))
        if server_name == "a":
            nested.append(await first.emit("demo", {"server_name": "b"}))
            nested.append(await second.emit("demo", {"server_name": "a"}))

    first.subscribe("demo", listener)
    result = await first.emit("demo", {"server_name": "a"})
    assert result.status == "completed"
    assert [r.status for r in nested] == [
        "suppressed",
        "suppressed",
        "completed",
        "completed",
    ]
    assert first.diagnostics().suppressed == 2
    assert not first.diagnostics().active


async def test_failures_are_isolated_and_before_hooks_fail_closed():
    bus = EventBus(
        EventOptions(listener_timeout_seconds=0.01, hook_timeout_seconds=0.01)
    )
    bus.registry.register(EventDefinition(name="before_demo", phase="before"))

    async def stall(**kwargs):
        await asyncio.Event().wait()

    bus.subscribe("*", stall)
    control = CancellableEvent()
    before = await bus.emit("before_demo", {"event": control})
    assert before.status == "cancelled" and control.is_cancelled
    assert before.failures[0].code == "event_listener_timeout"
    control.seal()
    control.cancel("late change")
    assert control.cancel_reason == "A before-operation listener did not complete"
    after = await bus.emit("after_demo")
    assert after.status == "partial"
    assert after.failures[0].error_type == "TimeoutError"


async def test_correlation_and_stale_child_context_do_not_suppress_new_work():
    bus = EventBus()
    release = asyncio.Event()
    child = None
    calls = 0

    async def deferred():
        await release.wait()
        return await bus.emit("demo")

    async def listener():
        nonlocal child, calls
        calls += 1
        if calls == 1:
            child = asyncio.create_task(deferred())

    bus.subscribe("demo", listener)
    with correlation_scope():
        first = await bus.emit("demo")
        second = await bus.emit("other")
    release.set()
    third = await child
    assert first.correlation_id == second.correlation_id
    assert third.status == "completed"
    assert third.parent_event_id is None


async def test_owner_lifetime_rejects_stale_generation_and_cross_owner_unsubscribe():
    bus = EventBus()
    generation = bus.open_owner("plugin:demo")
    token = bus.subscribe(
        "demo", lambda: None, owner="plugin:demo", generation=generation
    )
    with pytest.raises(PermissionError):
        bus.unsubscribe(token, owner="plugin:other")
    bus.remove_owner("plugin:demo")
    bus.open_owner("plugin:demo")
    with pytest.raises(RuntimeError):
        bus.subscribe("demo", lambda: None, owner="plugin:demo", generation=generation)
    assert not bus.events_for_owner("plugin:demo")


async def test_typed_events_validate_before_delivery_and_mask_secrets():
    class Payload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        count: int
        password: SecretStr

    bus = EventBus()
    bus.registry.register(EventDefinition(name="demo:typed"), Payload)
    seen = []
    bus.subscribe("*", lambda event: seen.append(event), observer=True)
    with pytest.raises(ValidationError):
        await bus.emit(
            "demo:typed",
            {"count": "invalid", "password": "payload-password-must-not-appear"},
        )
    assert not seen
    await bus.emit(
        "demo:typed", {"count": 1, "password": "payload-password-must-not-appear"}
    )
    assert seen[0].data["password"] != "payload-password-must-not-appear"
    assert "payload-password-must-not-appear" not in bus.diagnostics().model_dump_json()


async def test_active_diagnostics_and_owner_drain():
    bus = EventBus()
    entered, release = asyncio.Event(), asyncio.Event()

    async def callback():
        entered.set()
        await release.wait()

    bus.subscribe("demo", callback, owner="plugin:demo")
    pending = asyncio.create_task(bus.emit("demo"))
    await entered.wait()
    assert bus.diagnostics().active[0].status == "dispatching"
    bus.deactivate_owner("plugin:demo")
    drain = asyncio.create_task(bus.drain_owner("plugin:demo", 1))
    await asyncio.sleep(0)
    assert not drain.done()
    release.set()
    await pending
    await drain
    bus.remove_owner("plugin:demo")
    assert not bus.diagnostics().active


async def test_capacity_failure_is_visible_without_invalidating_notification():
    bus = EventBus(EventOptions(max_active=1))
    entered, release = asyncio.Event(), asyncio.Event()

    async def callback():
        entered.set()
        await release.wait()

    bus.subscribe("demo", callback)
    first = asyncio.create_task(bus.emit("demo"))
    await entered.wait()
    result = await bus.emit("other")
    assert result.status == "partial"
    assert result.failures[0].owner == "event-bus"
    release.set()
    await first


async def test_plugin_namespace_registration_and_reload_cleanup(
    app_context, plugin_factory
):
    plugin = await plugin_factory(
        "typed_events",
        """
from pydantic import BaseModel
from bedrock_server_manager.plugins import PluginBase
class Payload(BaseModel):
    count: int
class Events(PluginBase):
    def on_load(self):
        self.received = []
        self.api.events.define("typed_events:changed", Payload)
        self.api.events.listen("typed_events:changed", self.changed)
    async def changed(self, count, **kwargs):
        self.received.append(count)
""",
    )
    stale_api = plugin.api
    result = await plugin.api.events.emit("typed_events:changed", count=2)
    assert result.status == "completed" and plugin.received == [2]
    assert (
        app_context.events.registry.definition("typed_events:changed").owner
        == "plugin:typed_events"
    )
    with pytest.raises(ValueError):
        await plugin.api.events.emit("before_server_start", server_name="example")
    await app_context.plugin_manager.unload_plugin_by_name("typed_events")
    assert not app_context.events.registry.declared("typed_events:changed")
    assert await app_context.plugin_manager.load_plugin_by_name("typed_events")
    with pytest.raises(RuntimeError):
        stale_api.events.listen("typed_events:changed", lambda **kwargs: None)
    with pytest.raises(RuntimeError):
        await stale_api.events.emit("typed_events:changed", count=4)


async def test_core_status_and_player_events_do_not_use_api_facade(
    app_context, real_bedrock_server, monkeypatch
):
    from bedrock_server_manager.context import AppContext
    from bedrock_server_manager.events.player import publish_player_snapshot

    monkeypatch.setattr(
        AppContext,
        "api",
        property(
            lambda self: (_ for _ in ()).throw(
                AssertionError("Core event used API facade")
            )
        ),
    )
    seen = []
    app_context.events.subscribe(
        "*", lambda event: seen.append(event), observer=True, owner="test"
    )
    await real_bedrock_server.set_status_in_config("STOPPED")
    await publish_player_snapshot(
        app_context,
        server_name=real_bedrock_server.server_name,
        player_count=0,
        players=[],
    )
    assert [event.name for event in seen] == [
        "before_server_status_change",
        "after_server_status_change",
        "after_server_players_change",
    ]
    assert seen[0].correlation_id == seen[1].correlation_id
    assert seen[2].data["result"]["player_count"] == 0


async def test_constructor_failure_removes_listener_and_payload_definitions(
    app_context,
):
    directory = app_context.plugin_manager.plugin_dirs[0]
    (directory / "broken_events.py").write_text("""
from pydantic import BaseModel
from bedrock_server_manager.plugins import PluginBase
class Payload(BaseModel):
    value: int
class Broken(PluginBase):
    version = "1.0.0"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api.events.define("broken_events:changed", Payload)
        self.api.events.listen("broken_events:changed", lambda **kwargs: None)
        raise RuntimeError("Constructor failed")
""")
    await app_context.plugin_service.register_or_update_plugin(
        "broken_events", enabled=True
    )
    assert not await app_context.plugin_manager.load_plugin_by_name("broken_events")
    assert not app_context.events.registry.declared("broken_events:changed")
    assert not app_context.events.events_for_owner("plugin:broken_events")
