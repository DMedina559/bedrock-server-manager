"""Event diagnostics and scoped subscription helpers through real dispatch."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import BaseModel, ValidationError

from bedrock_server_manager.events import (
    EventActivityQuery,
    EventBus,
    EventDefinition,
    EventDispatchRejected,
    EventOptions,
    EventRegistry,
)
from bedrock_server_manager.events.models import EventDelivery, EventEnvelope


async def test_once_is_consumed_before_overlapping_delivery():
    bus = EventBus()
    entered, release = asyncio.Event(), asyncio.Event()
    seen = []

    async def listener(value):
        seen.append(value)
        entered.set()
        await release.wait()

    token = bus.once("example", listener)
    first = asyncio.create_task(bus.emit("example", {"value": 1}))
    await entered.wait()
    second = await bus.emit("example", {"value": 2})
    assert second.listeners_called == 0
    release.set()
    receipt = await first
    assert seen == [1]
    assert receipt.listeners[0].subscription_id == token
    assert receipt.listeners[0].status == "completed"
    assert receipt.listeners[0].duration_ms >= 0
    assert receipt.listeners[0].listener_name.endswith("listener")
    assert bus.diagnostics().subscriptions == 0


async def test_wait_for_predicate_timeout_cancel_and_owner_cleanup():
    bus = EventBus()
    waiter = asyncio.create_task(
        bus.wait_for("example", predicate=lambda value: value > 1)
    )
    await asyncio.sleep(0)
    await bus.emit("example", {"value": 1})
    assert not waiter.done()
    await bus.emit("example", {"value": 2})
    assert await waiter == {"value": 2}
    assert bus.diagnostics().subscriptions == 0
    with pytest.raises(TimeoutError):
        await bus.wait_for("example", timeout=0.01)
    assert bus.diagnostics().subscriptions == 0
    waiter = asyncio.create_task(bus.wait_for("example"))
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert bus.diagnostics().subscriptions == 0
    waiter = asyncio.create_task(bus.wait_for("example", owner="plugin:test"))
    await asyncio.sleep(0)
    bus.remove_owner("plugin:test")
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert bus.diagnostics().subscriptions == 0
    waiter = asyncio.create_task(bus.wait_for("example"))
    await asyncio.sleep(0)
    await bus.close()
    with pytest.raises(asyncio.CancelledError):
        await waiter


async def test_predicate_error_does_not_fail_event_and_cleans_listener():
    bus = EventBus()

    def predicate(**data):
        raise ValueError("Bad predicate")

    waiter = asyncio.create_task(bus.wait_for("example", predicate=predicate))
    await asyncio.sleep(0)
    assert (await bus.emit("example")).status == "completed"
    with pytest.raises(ValueError, match="Bad predicate"):
        await waiter
    assert bus.diagnostics().subscriptions == 0


async def test_listener_failure_and_active_diagnostics_filters():
    bus = EventBus(EventOptions(listener_timeout_seconds=0.01))

    async def slow(**data):
        await asyncio.Event().wait()

    bus.subscribe("example", slow, owner="plugin:slow")
    first = await bus.emit("example")
    assert first.listeners[0].status == "timed_out"
    assert first.listeners[0].failure.code == "event_listener_timeout"
    assert first.listeners[0].duration_ms >= 0
    await bus.emit("other")
    query = EventActivityQuery(
        owner="plugin:slow",
        name="example",
        status="partial",
        correlation_id=first.correlation_id,
        limit=1,
    )
    assert [record.event_id for record in bus.diagnostics(query).recent] == [
        first.event_id
    ]
    assert (
        bus.diagnostics(EventActivityQuery(status="completed")).recent[0].name
        == "other"
    )
    assert bus.diagnostics(EventActivityQuery(name="missing")).recent == []


async def test_dispatch_rejection_reasons_and_depth_fail_closed():
    bus = EventBus(EventOptions(max_depth=1))
    controls = []
    from bedrock_server_manager.events import CancellableEvent

    async def nested(**data):
        same = await bus.emit("root")
        assert same.rejection_reason == "recursion"
        control = CancellableEvent()
        controls.append(control)
        receipt = await bus.emit("child", {"event": control})
        assert receipt.rejection_reason == "depth_limit"
        assert receipt.failures[0].code == "event_depth_limit"
        assert receipt.cancellation_reason

    bus.subscribe("root", nested)
    await bus.emit("root")
    assert controls[0].is_cancelled
    assert bus.diagnostics().failed_listeners == 0
    await bus.close()
    with pytest.raises(EventDispatchRejected) as error:
        await bus.emit("root")
    assert error.value.record.rejection_reason == "shutdown"
    assert bus.diagnostics().recent[-1].rejection_reason == "shutdown"


class Payload(BaseModel):
    value: int


class OtherPayload(BaseModel):
    label: str


def test_registry_ownership_variants_and_cached_adapter(monkeypatch):
    registry = EventRegistry()
    definition = EventDefinition(name="example", owner="plugin:one")
    registry.register(definition, Payload)
    with pytest.raises(ValueError):
        registry.register(
            definition.model_copy(update={"owner": "plugin:two"}), Payload
        )
    with pytest.raises(ValueError):
        registry.register(definition, OtherPayload)
    child = EventRegistry(registry)
    with pytest.raises(ValueError):
        child.register(definition, OtherPayload, allow_variants=True)
    import bedrock_server_manager.events.registry as module

    def no_new_adapter(*args, **kwargs):
        raise AssertionError("Validator rebuilt during dispatch")

    with monkeypatch.context() as patch:
        patch.setattr(module, "TypeAdapter", no_new_adapter)
        assert registry.prepare("example", {"value": "2"}).value == 2
        assert registry.prepare("example", {"value": 3}).value == 3
    registry.register(definition, OtherPayload, allow_variants=True)
    assert registry.prepare("example", {"label": "hello"}).label == "hello"


def test_registry_concurrent_read_write_and_removal():
    registry = EventRegistry()

    def run(index):
        name = f"plugin{index}:event"
        registry.register(EventDefinition(name=name, owner=f"plugin:{index}"), Payload)
        for _ in range(10):
            registry.catalog()
            assert registry.prepare(name, {"value": index}).value == index
        registry.remove_owner(f"plugin:{index}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(run, range(16)))
    assert registry.catalog().events == []


@pytest.mark.parametrize(
    "revision",
    [
        {"epoch": "test"},
        {"revision": 1},
        {"epoch": "", "revision": 1},
        {"epoch": "test", "revision": 0},
    ],
)
def test_envelope_rejects_incoherent_revisions(revision):
    with pytest.raises(ValidationError):
        EventEnvelope(
            event_id="one",
            correlation_id="two",
            timestamp=1,
            source="test",
            name="test",
            data={},
            **revision,
        )


def test_delivery_reuses_count_invariant():
    with pytest.raises(ValidationError):
        EventDelivery(owner="transport:test", targeted=2, sent=1)
    assert (
        EventDelivery(owner="transport:test", targeted=2, sent=1, failed=1).failed == 1
    )


async def test_plugin_helpers_receive_private_events_and_cancel_on_unload(
    app_context, plugin_factory
):
    plugin = await plugin_factory(
        "private_events",
        """
from pydantic import BaseModel
from bedrock_server_manager.plugins import PluginBase
class Payload(BaseModel):
    value: int
class Private(PluginBase):
    version = "1.0"
    def on_load(self):
        self.api.events.define("private_events:changed", Payload, public=False)
""",
    )
    seen = []
    plugin.api.events.once(
        "private_events:changed", lambda **data: seen.append(data["value"])
    )
    waiter = asyncio.create_task(
        plugin.api.events.wait_for(
            "private_events:changed", predicate=lambda **data: data["value"] == 2
        )
    )
    await asyncio.sleep(0)
    await plugin.api.events.emit("private_events:changed", value=1)
    await plugin.api.events.emit("private_events:changed", value=2)
    assert (await waiter)["value"] == 2
    assert seen == [1]
    waiter = asyncio.create_task(plugin.api.events.wait_for("private_events:changed"))
    await asyncio.sleep(0)
    await app_context.plugin_manager.unload_plugin_by_name("private_events")
    with pytest.raises(asyncio.CancelledError):
        await waiter


async def test_once_and_persistent_listener_are_distinct_subscriptions():
    bus = EventBus()
    values = []

    async def receive(value):
        values.append(value)

    bus.subscribe("example", receive)
    bus.once("example", receive)
    assert (await bus.emit("example", {"value": 1})).listeners_called == 2
    assert (await bus.emit("example", {"value": 2})).listeners_called == 1
    assert values == [1, 1, 2]


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
async def test_waiter_rejects_unbounded_or_invalid_timeout(timeout):
    bus = EventBus()
    with pytest.raises(ValueError):
        await bus.wait_for("example", timeout=timeout)
    assert bus.diagnostics().subscriptions == 0


async def test_listeners_and_observers_receive_same_normalized_contract_fields():
    bus = EventBus()
    bus.registry.register(EventDefinition(name="typed:changed"), Payload)
    listeners, observers = [], []
    bus.subscribe("typed:changed", lambda **data: listeners.append(data))
    bus.subscribe(
        "typed:changed",
        lambda event: observers.append(event.data),
        observer=True,
        owner="transport:test",
    )
    await bus.emit("typed:changed", {"value": "2", "ignored": object()})
    assert listeners == observers == [{"value": 2}]


async def test_native_custom_emission_requires_own_declaration():
    from bedrock_server_manager.events.capabilities import create_event_capabilities

    class Payload(BaseModel):
        count: int

    bus = EventBus()
    bus.open_owner("plugin:owner")
    _, legacy, dispatch = create_event_capabilities("owner", bus)
    for name in ("owner:undeclared", "other:undeclared", "undeclared"):
        with pytest.raises(ValueError, match="own declared"):
            dispatch("emit", name)
    dispatch("define", "owner:changed", Payload)
    assert (await dispatch("emit", "owner:changed", count=1)).status == "completed"
    bus.define(EventDefinition(name="other:changed", owner="plugin:other"), Payload)
    with pytest.raises(ValueError, match="own declared"):
        dispatch("emit", "other:changed", count=1)
    with pytest.raises(ValueError, match="own declared"):
        await legacy("legacy_event", count=1)
    assert (await legacy("owner:changed", count=1)).status == "completed"
