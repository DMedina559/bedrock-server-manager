"""Core publications and plugin lifetimes use explicit event dependencies."""

import asyncio
import subprocess
import sys
from dataclasses import dataclass

import pytest

from bedrock_server_manager.events import (
    EventBus,
    EventDefinition,
    EventOptions,
    PlayerSnapshot,
    trigger_event,
)
from bedrock_server_manager.events.models import EventDelivery
from bedrock_server_manager.events.player import publish_player_snapshot
from bedrock_server_manager.results import DeliveryResult


class PublisherOnly:
    """Expose no context, registry, plugin manager, or transport."""

    def __init__(self, bus):
        self._bus = bus

    @property
    def accepting(self):
        return self._bus.accepting

    async def emit(self, *args, **kwargs):
        return await self._bus.emit(*args, **kwargs)


async def test_player_publication_is_typed_and_standalone():
    bus = EventBus()
    received = []
    bus.subscribe("after_server_players_change", lambda **data: received.append(data))
    snapshot = PlayerSnapshot(server_name="example", player_count=0, players=[])
    receipt = await publish_player_snapshot(PublisherOnly(bus), snapshot)
    assert receipt.status == "completed"
    assert received[0]["request"] == snapshot
    assert received[0]["result"].player_count == 0


async def test_status_configuration_needs_only_publisher(
    real_bedrock_server, app_context
):
    assert not hasattr(real_bedrock_server, "app_context")
    result = await real_bedrock_server.configuration.set_status(
        "TEST_STATUS", PublisherOnly(app_context.events)
    )
    assert result.new_status == "TEST_STATUS"
    assert await real_bedrock_server.get_status_from_config() == "TEST_STATUS"


async def test_monitor_retries_rejected_publication_without_replaying_delivered_listeners(
    app_context, real_bedrock_server
):
    bus = EventBus(EventOptions(max_active=1))
    entered, release = asyncio.Event(), asyncio.Event()

    async def block():
        entered.set()
        await release.wait()

    bus.subscribe("busy", block)
    occupied = asyncio.create_task(bus.emit("busy"))
    await entered.wait()
    manager = app_context.bedrock_process_manager
    manager.events = PublisherOnly(bus)
    try:
        await manager._publish_players(real_bedrock_server)
        assert real_bedrock_server.server_name in manager._pending_player_events
    finally:
        release.set()
        await occupied
    received = []
    bus.subscribe("after_server_players_change", lambda **data: received.append(data))

    def fail(**data):
        raise RuntimeError("Listener failed")

    bus.subscribe("after_server_players_change", fail, owner="fault")
    await manager._publish_players(real_bedrock_server)
    assert len(received) == 1
    assert real_bedrock_server.server_name not in manager._pending_player_events
    assert bus.diagnostics().recent[-1].status == "partial"


async def test_native_capabilities_remain_bound_to_original_bus_after_runtime_restart(
    app_context, plugin_factory
):
    old = await plugin_factory(
        "restart_events",
        """
from bedrock_server_manager.plugins import PluginBase
class Restart(PluginBase):
    version = "1.0"
""",
    )
    stale = old.api
    original = app_context.events
    await app_context.shutdown()
    await app_context.load()
    await app_context.plugin_manager.load_plugins()
    assert app_context.events is not original
    assert app_context.events.owner_generation("plugin:restart_events") == 1
    for operation in (
        lambda: stale.events.listen("restart_events:test", lambda **data: None),
        lambda: stale.events.once("restart_events:test", lambda **data: None),
        lambda: stale.events.diagnostics(),
    ):
        with pytest.raises(RuntimeError):
            operation()
    with pytest.raises(RuntimeError):
        await stale.events.emit("restart_events:test")
    with pytest.raises(RuntimeError):
        await stale.events.wait_for("restart_events:test", timeout=0.01)
    current = next(
        plugin
        for plugin in app_context.plugin_manager.plugins
        if plugin.api._plugin_name == "restart_events"
    )
    assert (await current.api.events.emit("restart_events:test")).status == "completed"


async def test_callable_objects_and_bound_method_wildcard_dedup():
    bus = EventBus()

    @dataclass
    class Callback:
        count: int = 0

        def __call__(self, **data):
            self.count += 1

        def handle(self, **data):
            self.count += 1

    callback = Callback()
    bus.subscribe("demo", callback)
    bus.subscribe("*", callback)
    bus.subscribe("demo", callback.handle)
    bus.subscribe("*", callback.handle)
    second = Callback()
    bus.subscribe("demo", second)
    result = await bus.emit("demo")
    assert result.listeners_called == 3
    assert callback.count == 2
    assert second.count == 1


@pytest.mark.parametrize("field", ["event", "app_context", "current_user"])
def test_reserved_payload_names_rejected_during_declaration(field):
    from pydantic import create_model

    model = create_model("Reserved", **{field: (str, ...)})
    bus = EventBus()
    with pytest.raises(ValueError, match="reserved"):
        bus.registry.register(EventDefinition(name="reserved:payload"), model)
    assert not bus.registry.declared("reserved:payload")


def test_delivery_aggregation_has_explicit_owner_semantics():
    one = EventDelivery(owner="transport:test", targeted=2, sent=1, failed=1)
    two = EventDelivery(owner="transport:test", targeted=1, unavailable=1)
    receipt = EventDelivery.combine([one, two])
    assert receipt.owner == "transport:test"
    assert (receipt.targeted, receipt.sent, receipt.failed, receipt.unavailable) == (
        3,
        1,
        1,
        1,
    )
    for items in ([], [one, EventDelivery(owner="other")], [DeliveryResult()]):
        with pytest.raises(ValueError):
            EventDelivery.combine(items)


async def test_operation_hooks_accept_explicit_bus_without_context():
    bus = EventBus()
    observed = []
    bus.subscribe("*", lambda **data: observed.append(data))

    @trigger_event(before="before_explicit", after="after_explicit")
    async def operation(value: int, *, events: EventBus):
        return value + 1

    assert await operation(2, events=bus) == 3
    assert len(observed) == 2
    assert all("events" not in data for data in observed)


def test_event_import_does_not_bootstrap_api_plugins_or_http():
    source = """
import sys
from bedrock_server_manager.events import EventBus
for name in ("bedrock_server_manager.api", "bedrock_server_manager.plugins", "bedrock_server_manager.web"):
    assert name not in sys.modules, name
from bedrock_server_manager import PluginBase, app_event, task_loop
assert callable(app_event) and callable(task_loop)
from bedrock_server_manager.plugins.api_bridge import create_app_api
assert create_app_api("example", None).list_available_apis()
"""
    result = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


async def test_timed_out_sync_listener_remains_owned_until_worker_finishes():
    import threading

    bus = EventBus(EventOptions(listener_timeout_seconds=0.01))
    entered, release, cancelled = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )

    def callback(*, cancellation_event):
        entered.set()
        cancellation_event.wait()
        cancelled.set()
        release.wait()

    bus.subscribe("worker", callback, owner="plugin:worker")
    try:
        receipt = await bus.emit("worker")
        assert entered.is_set()
        assert receipt.listeners[0].status == "timed_out"
        assert await asyncio.to_thread(cancelled.wait, 1)
        bus.deactivate_owner("plugin:worker")
        drain = asyncio.create_task(bus.drain_owner("plugin:worker", 1))
        await asyncio.sleep(0)
        assert not drain.done()
    finally:
        release.set()
    await drain
    bus.remove_owner("plugin:worker")
    await bus.close()


async def test_transport_failure_receipts_are_retained_without_payload_history():
    bus = EventBus()

    async def failed_transport(event):
        return DeliveryResult(targeted=2, sent=1, failed=1)

    bus.subscribe("*", failed_transport, owner="transport:test", observer=True)
    receipt = await bus.emit("transport:changed", {"private": "not-retained"})
    assert receipt.status == "partial"
    assert receipt.deliveries[0].failed == 1
    assert receipt.listeners[0].status == "failed"
    assert "not-retained" not in bus.diagnostics().model_dump_json()
