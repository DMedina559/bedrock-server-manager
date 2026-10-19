"""Public plugin event capabilities coexist with unchanged 4.0 callback contracts."""

import asyncio
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError

from bedrock_server_manager.api.server import start_server
from bedrock_server_manager.error import APICancelledError
from bedrock_server_manager.events import EventFilter, EventOptions, PluginEvent

SOURCE = "from bedrock_server_manager import PluginBase\nclass Access(PluginBase):\n    version = '1.0'\n"


class StartPayload(BaseModel):
    server_name: str


class ValuePayload(BaseModel):
    value: int


async def test_legacy_typed_and_observer_delivery_coexist(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)
    seen = []

    async def legacy(server_name, request, event):
        seen.append(("legacy", server_name, request.server_name, event.is_cancelled))

    async def typed(event: PluginEvent[StartPayload]):
        assert event.payload.server_name == real_bedrock_server.server_name
        assert event.operation is not None
        assert event.sequence is not None
        assert event.operation.name == "server.start"
        assert event.sequence.sequence_id == event.operation.sequence_id
        assert event.context.phase == "before"
        assert event.can_cancel
        assert 0 < event.remaining_seconds <= 120
        seen.append(("typed", event.context.event_id))

    async def observer(event: PluginEvent[StartPayload]):
        assert event.context.observer
        assert not event.can_cancel
        with pytest.raises(RuntimeError):
            event.cancel("Observers cannot veto")
        with pytest.raises(TypeError):
            cast(dict[str, Any], event.data)["server_name"] = "changed"
        with pytest.raises(TypeError):
            event.data["request"]["server_name"] = "changed"
        event.payload.server_name = "detached copy"
        assert event.data["server_name"] == real_bedrock_server.server_name
        seen.append(("observer", event.context.event_id))

    plugin.api.events.listen("before_server_start", legacy)
    plugin.api.events.listen_typed("before_server_start", StartPayload, typed)
    plugin.api.events.observe(
        "before_server_start", observer, payload_model=StartPayload
    )
    response = await start_server(
        {"server_name": real_bedrock_server.server_name}, app_context=app_context
    )
    assert response.outcome == "started"
    assert [item[0] for item in seen] == ["legacy", "typed", "observer"]
    assert seen[1][1] == seen[2][1]
    assert plugin.api.events.current() is None
    with pytest.raises(RuntimeError):
        plugin.api.events.handler()


async def test_typed_hook_cancels_but_escaped_context_cannot(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)
    captured = []

    async def capture(event):
        captured.append(event)

    async def cancel(event):
        assert not captured[0].can_cancel
        with pytest.raises(RuntimeError):
            captured[0].cancel("Expired handler")
        event.cancel("Policy denied")
        assert event.is_cancelled
        assert event.cancel_reason == "Policy denied"

    plugin.api.events.hook("before_server_start", capture, priority=10)
    plugin.api.events.hook("before_server_start", cancel)
    with pytest.raises(APICancelledError, match="Policy denied"):
        await start_server(
            {"server_name": real_bedrock_server.server_name}, app_context=app_context
        )
    assert not await real_bedrock_server.is_running()
    assert not captured[0].can_cancel


async def test_catalog_privacy_and_owned_private_observers(app_context, plugin_factory):
    one = await plugin_factory("one", SOURCE)
    two = await plugin_factory("two", SOURCE)
    one.api.events.define("one:private", ValuePayload, public=False)
    one.api.events.define("one:public", ValuePayload)
    own_names = {item.name for item in one.api.events.catalog().events}
    other_names = {item.name for item in two.api.events.catalog().events}
    assert "one:private" in own_names
    assert "one:private" not in other_names
    assert "one:public" in other_names
    assert "on_load" in own_names
    definition = one.api.events.describe("one:private")
    assert definition.payload_schema["properties"]["value"]["type"] == "integer"
    definition.payload_schema.clear()
    assert one.api.events.describe("one:private").payload_schema
    with pytest.raises(PermissionError):
        two.api.events.describe("one:private")
    with pytest.raises(KeyError):
        one.api.events.describe("missing")
    with pytest.raises(PermissionError):
        two.api.events.observe("one:private", lambda event: None)
    seen = []
    one.api.events.observe(
        "one:private", lambda event: seen.append(event.payload.value)
    )
    await one.api.events.emit("one:private", value=7)
    assert seen == [7]


async def test_filters_and_predicate_do_not_consume_once_on_mismatch(
    app_context, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)
    seen = []
    predicate_seen = []

    def predicate(event):
        predicate_seen.append(event.data["value"])
        assert "event" not in event.data
        return event.data["value"] > 1

    plugin.api.events.once(
        "filtered",
        lambda **data: seen.append(data["value"]),
        filters=EventFilter(
            server_name="selected", source="application", operation_name="example"
        ),
        predicate=predicate,
    )
    with app_context.operations.scope("example"):
        await app_context.events.emit("filtered", {"server_name": "other", "value": 3})
        await app_context.events.emit(
            "filtered", {"server_name": "selected", "value": 1}
        )
        await app_context.events.emit(
            "filtered", {"server_name": "selected", "value": 2}
        )
        await app_context.events.emit(
            "filtered", {"server_name": "selected", "value": 3}
        )
    assert seen == [2]
    assert predicate_seen == [1, 2]
    assert not plugin.api.events.subscriptions()


async def test_ordering_forward_references_cycle_rollback_and_stats(
    app_context, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)
    order = []

    async def first(**data):
        order.append("first")

    async def second(**data):
        order.append("second")

    token = plugin.api.events.listen(
        "ordered", second, listener_id="second", after=("first",), priority=100
    )
    plugin.api.events.listen("ordered", first, listener_id="first", priority=-100)
    await app_context.events.emit("ordered")
    assert order == ["first", "second"]
    snapshots = plugin.api.events.subscriptions()
    assert snapshots[0].subscription_id == token
    assert snapshots[0].listener_id == "access:second"
    assert snapshots[0].calls == 1
    assert snapshots[0].last_status == "completed"
    snapshots[0].calls = 999
    assert plugin.api.events.subscriptions()[0].calls == 1
    with pytest.raises(ValueError, match="cycle"):
        plugin.api.events.listen(
            "ordered", first, listener_id="cycle", after=("cycle",)
        )
    with pytest.raises(ValueError, match="already registered"):
        plugin.api.events.listen("ordered", first, listener_id="second")
    with pytest.raises(ValueError, match="namespace"):
        plugin.api.events.listen("ordered", first, listener_id="another:stolen")
    assert len(plugin.api.events.subscriptions()) == 2


async def test_temporary_subscription_exit_exception_and_unload(
    app_context, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)
    seen = []
    with plugin.api.events.subscription("temporary", lambda **data: seen.append(1)):
        await app_context.events.emit("temporary")
    await app_context.events.emit("temporary")
    assert seen == [1]
    with pytest.raises(ValueError):
        with plugin.api.events.subscription("temporary", lambda **data: None):
            raise ValueError("cleanup")
    assert not plugin.api.events.subscriptions()
    with plugin.api.events.subscription("temporary", lambda **data: None):
        app_context.events.remove_owner("plugin:access")
    with pytest.raises(RuntimeError):
        plugin.api.events.catalog()


async def test_plugin_operation_namespace_and_outcomes(app_context, plugin_factory):
    plugin = await plugin_factory("access", SOURCE)
    with app_context.operations.scope("root") as root:
        with plugin.api.operations.scope("access:upload") as operation:
            assert operation.parent_operation_id == root.snapshot.operation_id
            assert operation.owner == "plugin:access"
            with pytest.raises(ValidationError):
                operation.name = "backup.create"
        with pytest.raises(ValueError):
            with plugin.api.operations.scope("access:failed"):
                raise ValueError("domain failure")
        results = plugin.api.operations.results()
        assert results[0].outcome == "completed"
        assert results[1].status == "failed"
        with pytest.raises(ValueError, match="namespace"):
            with plugin.api.operations.scope("backup.create"):
                pass
    assert plugin.api.operations.current() is None
    scope = plugin.api.operations.scope("access:stale")
    app_context.events.remove_owner("plugin:access")
    with pytest.raises(RuntimeError):
        with scope:
            pass


async def test_nested_handler_deadline_and_observer_failure_isolation(
    app_context, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)
    views = []

    async def outer(event):
        views.append(event)
        await app_context.events.emit("inner")

    async def inner(event):
        assert event.remaining_seconds <= views[0].remaining_seconds + 0.01

    async def broken(event):
        raise RuntimeError("Observer failed")

    plugin.api.events.hook("outer", outer)
    plugin.api.events.hook("inner", inner)
    plugin.api.events.observe("outer", broken)
    receipt = await app_context.events.emit("outer")
    assert receipt.listeners[0].status == "completed"
    assert receipt.listeners[1].status == "failed"
    stats = plugin.api.events.subscriptions()[-1]
    assert stats.kind == "observer"
    assert stats.failures == 1


async def test_predicate_errors_are_bounded_and_fail_closed(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)

    def broken(_event):
        raise ValueError("Filter failed")

    plugin.api.events.hook("before_server_start", lambda event: None, predicate=broken)
    with pytest.raises(APICancelledError):
        await start_server(
            {"server_name": real_bedrock_server.server_name}, app_context=app_context
        )
    assert plugin.api.events.subscriptions()[0].failures == 1


async def test_observer_timeout_stats_and_callback_cleanup(app_context, plugin_factory):
    plugin = await plugin_factory("access", SOURCE)
    app_context.events.options = EventOptions(listener_timeout_seconds=0.01)
    captured = []

    async def slow(event):
        captured.append(event)
        await asyncio.Event().wait()

    plugin.api.events.observe("slow", slow)
    await app_context.events.emit("slow")
    assert plugin.api.events.subscriptions()[0].timeouts == 1
    assert not captured[0].can_cancel
    assert captured[0].remaining_seconds == 0


async def test_async_subscription_cleans_up_on_task_cancellation(
    app_context, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)
    entered = asyncio.Event()

    async def watch():
        async with plugin.api.events.subscription(
            "temporary", lambda event: None, mode="observer"
        ):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(watch())
    await entered.wait()
    assert len(plugin.api.events.subscriptions()) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not plugin.api.events.subscriptions()


async def test_decorator_filters_and_ordering_preserve_legacy_arguments(
    app_context, plugin_factory
):
    plugin = await plugin_factory(
        "decorated",
        """
from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.events import EventFilter
class Decorated(PluginBase):
    version = "1.0"
    @app_event("on_load")
    async def loaded(self):
        self.seen = []
    @app_event("decorated", listener_id="second", after=("first",), priority=100,
               filters=EventFilter(server_name="selected"))
    async def second(self, server_name):
        self.seen.append(("second", server_name))
    @app_event("decorated", listener_id="first", priority=-100,
               filters=EventFilter(server_name="selected"))
    async def first(self, server_name):
        self.seen.append(("first", server_name))
""",
    )
    await app_context.events.emit("decorated", {"server_name": "other"})
    assert plugin.seen == []
    await app_context.events.emit("decorated", {"server_name": "selected"})
    assert plugin.seen == [("first", "selected"), ("second", "selected")]


async def test_unhandled_observer_veto_does_not_cancel_start(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)

    async def veto(event):
        event.cancel("Not allowed for observers")

    plugin.api.events.observe("before_server_start", veto, listener_id="observer")
    with pytest.raises(ValueError, match="stages"):
        plugin.api.events.hook(
            "before_server_start",
            lambda event: None,
            listener_id="hook",
            after=("observer",),
        )
    response = await start_server(
        {"server_name": real_bedrock_server.server_name}, app_context=app_context
    )
    assert response.outcome == "started"
    assert plugin.api.events.subscriptions()[0].failures == 1


async def test_predicate_once_claim_is_atomic_across_overlapping_events(
    app_context, plugin_factory
):
    from threading import Barrier

    plugin = await plugin_factory("access", SOURCE)
    barrier = Barrier(2, timeout=2)
    seen = []

    def predicate(event):
        barrier.wait()
        return True

    plugin.api.events.once(
        "overlap", lambda **data: seen.append(1), predicate=predicate
    )
    first, second = await asyncio.gather(
        app_context.events.emit("overlap"), app_context.events.emit("overlap")
    )
    assert seen == [1]
    assert first.listeners_called + second.listeners_called == 1


async def test_new_capabilities_are_invalid_after_reload(app_context, plugin_factory):
    plugin = await plugin_factory("access", SOURCE)
    stale = plugin.api.events
    stale.observe("owned", lambda event: None)
    old_scope = stale.subscription("owned", lambda **data: None)
    await app_context.plugin_manager.reload_plugin("access")
    for operation in (
        stale.catalog,
        stale.subscriptions,
        lambda: stale.handler(),
        lambda: stale.hook("owned", lambda event: None),
        lambda: stale.observe("owned", lambda event: None),
    ):
        with pytest.raises(RuntimeError):
            operation()
    with pytest.raises(RuntimeError):
        with old_scope:
            pass


async def test_observers_read_cancellation_and_typed_context_preserves_positional_data(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)
    seen = []

    async def deny(event):
        event.cancel("Maintenance")

    async def inspect_cancelled(event):
        assert event.is_cancelled
        assert event.cancel_reason == "Maintenance"
        assert not event.can_cancel
        seen.append(event.context.name)

    plugin.api.events.hook("before_server_start", deny)
    plugin.api.events.observe("before_server_start", inspect_cancelled)
    with pytest.raises(APICancelledError):
        await start_server(
            {"server_name": real_bedrock_server.server_name}, app_context=app_context
        )
    plugin.api.events.observe("positional", lambda event: seen.append(event.arguments))
    await app_context.events.emit("positional", None, "argument", {"nested": [1, 2]})
    assert seen[0] == "before_server_start"
    assert seen[1][0] == "argument"
    assert seen[1][1]["nested"] == (1, 2)
    with pytest.raises(TypeError):
        seen[1][1]["nested"] = []


async def test_typed_wildcards_respect_private_contracts(app_context, plugin_factory):
    one = await plugin_factory("one", SOURCE)
    two = await plugin_factory("two", SOURCE)
    one.api.events.define("one:private", ValuePayload, public=False)
    one.api.events.define("one:public", ValuePayload)
    one_seen, two_seen = [], []
    one.api.events.observe("*", lambda event: one_seen.append(event.context.name))
    two.api.events.hook("*", lambda event: two_seen.append(event.context.name))
    await one.api.events.emit("one:private", value=1)
    await one.api.events.emit("one:public", value=2)
    assert one_seen == ["one:private", "one:public"]
    assert two_seen == ["one:public"]


async def test_cancellation_capability_cannot_escape_to_a_child_task(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)

    async def policy(event):
        async def child():
            assert not event.can_cancel
            with pytest.raises(RuntimeError):
                event.cancel("Child task veto")

        await asyncio.create_task(child())
        assert event.can_cancel
        event.cancel("Owner veto")

    plugin.api.events.hook("before_server_start", policy)
    with pytest.raises(APICancelledError, match="Owner veto"):
        await start_server(
            {"server_name": real_bedrock_server.server_name}, app_context=app_context
        )


@pytest.mark.parametrize("mode", ["legacy", "hook", "observer"])
@pytest.mark.parametrize("permanent_first", [False, True])
async def test_subscription_scopes_preserve_permanent_registration(
    app_context, plugin_factory, mode, permanent_first
):
    plugin = await plugin_factory("access", SOURCE)
    seen = []

    async def callback(*args, **kwargs):
        seen.append(1)

    register = {
        "legacy": plugin.api.events.listen,
        "hook": plugin.api.events.hook,
        "observer": plugin.api.events.observe,
    }[mode]
    options = dict(listener_id="shared")
    if permanent_first:
        permanent = register("shared", callback, **options)
    with plugin.api.events.subscription(
        "shared", callback, mode=mode, **options
    ) as outer:
        if not permanent_first:
            permanent = register("shared", callback, **options)
        with plugin.api.events.subscription(
            "shared", callback, mode=mode, **options
        ) as inner:
            assert outer == inner == permanent
            await app_context.events.emit("shared")
        await app_context.events.emit("shared")
    await app_context.events.emit("shared")
    assert seen == [1, 1, 1]
    assert [item.subscription_id for item in plugin.api.events.subscriptions()] == [
        permanent
    ]


@pytest.mark.parametrize("mode", ["legacy", "hook", "observer"])
async def test_overlapping_scopes_release_only_their_own_registration(
    app_context, plugin_factory, mode
):
    plugin = await plugin_factory("access", SOURCE)
    seen = []

    async def callback(*args, **kwargs):
        seen.append(1)

    first = plugin.api.events.subscription("shared", callback, mode=mode)
    second = plugin.api.events.subscription("shared", callback, mode=mode)
    first_token = first.__enter__()
    try:
        with second as second_token:
            assert first_token == second_token
            first.__exit__(None, None, None)
            await app_context.events.emit("shared")
        await app_context.events.emit("shared")
    finally:
        first.__exit__(None, None, None)
    assert seen == [1]
    assert not plugin.api.events.subscriptions()


@pytest.mark.parametrize("mode", ["hook", "observer"])
async def test_typed_duplicate_registration_and_payload_identity(
    app_context, plugin_factory, mode
):
    plugin = await plugin_factory("access", SOURCE)
    seen = []

    class Handler:
        async def callback(self, event):
            seen.append(type(event.payload))

    handler = Handler()
    register = getattr(plugin.api.events, "observe" if mode == "observer" else mode)
    first = register("typed", handler.callback, payload_model=ValuePayload)
    assert register("typed", handler.callback, payload_model=ValuePayload) == first
    assert register("typed", handler.callback, payload_model=StartPayload) != first
    await app_context.events.emit("typed", {"value": 3, "server_name": "example"})
    assert seen == [ValuePayload, StartPayload]


@pytest.mark.parametrize("removal", ["unsubscribe", "deactivate", "remove"])
async def test_listener_removed_during_predicate_does_not_start(
    app_context, plugin_factory, removal
):
    from threading import Event

    plugin = await plugin_factory("access", SOURCE)
    entered, release = Event(), Event()
    seen = []

    def predicate(event):
        entered.set()
        assert release.wait(5)
        return True

    async def callback(event):
        seen.append(1)

    token = plugin.api.events.hook("pending", callback, predicate=predicate)
    emission = asyncio.create_task(app_context.events.emit("pending"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if removal == "unsubscribe":
            plugin.api.events.unsubscribe(token)
        elif removal == "deactivate":
            app_context.events.deactivate_owner("plugin:access")
        else:
            app_context.events.remove_owner("plugin:access")
    finally:
        release.set()
        record = await emission
    assert seen == []
    assert record.listeners_called == 0
    assert not record.failures


@pytest.mark.parametrize("offset", [-10000, 10000])
async def test_handler_uses_event_loop_deadline_clock(
    app_context, plugin_factory, monkeypatch, offset
):
    from bedrock_server_manager.events import CancellableEvent, EventDefinition

    plugin = await plugin_factory("access", SOURCE)
    app_context.events.registry.register(
        EventDefinition(name="clock_before", phase="before")
    )
    seen = []

    async def callback(event):
        assert (
            0
            < event.remaining_seconds
            <= app_context.events.options.hook_timeout_seconds
        )
        assert event.can_cancel
        event.cancel("Clock test")
        seen.append(event.is_cancelled)

    plugin.api.events.hook("clock_before", callback)
    loop = asyncio.get_running_loop()
    original = loop.time
    with monkeypatch.context() as patch:
        patch.setattr(loop, "time", lambda: original() + offset)
        record = await app_context.events.emit(
            "clock_before", {"event": CancellableEvent()}
        )
    assert seen == [True]
    assert record.cancellation_reason == "Clock test"


@pytest.mark.parametrize("option", ["before", "after"])
@pytest.mark.parametrize(
    "value,error",
    [
        ("listener", TypeError),
        ((None,), TypeError),
        (("",), ValueError),
        (("foreign:",), ValueError),
    ],
)
async def test_invalid_ordering_references_fail_at_registration(
    plugin_factory, option, value, error
):
    plugin = await plugin_factory("access", SOURCE)
    with pytest.raises(error):
        plugin.api.events.listen("ordered", lambda **data: None, **{option: value})
    assert not plugin.api.events.subscriptions()


async def test_ordering_diagnostics_track_forward_reference_removal(
    app_context, plugin_factory
):
    plugin = await plugin_factory("access", SOURCE)

    async def callback(**kwargs):
        pass

    plugin.api.events.listen(
        "ordered", callback, listener_id="second", after=("first",)
    )
    assert plugin.api.events.subscriptions()[0].unresolved_after == ("access:first",)
    target = plugin.api.events.listen("ordered", callback, listener_id="first")
    assert plugin.api.events.subscriptions()[0].unresolved_after == ()
    plugin.api.events.unsubscribe(target)
    assert plugin.api.events.subscriptions()[0].unresolved_after == ("access:first",)


@pytest.mark.parametrize("existing_operation", [False, True])
async def test_custom_event_operations_inherit_correlation_and_match_filters(
    app_context, plugin_factory, existing_operation
):
    from contextlib import nullcontext

    from bedrock_server_manager.events.bus import current_correlation_id

    plugin = await plugin_factory("access", SOURCE)
    plugin.api.events.define("access:root", ValuePayload)
    plugin.api.events.define("access:child", ValuePayload)
    operations, children, filtered, receipts = [], [], [], []

    async def selected(event):
        filtered.append(event.context.correlation_id)

    async def child(event):
        children.append((event.context.correlation_id, event.operation.correlation_id))

    async def root(event):
        with plugin.api.operations.scope("access:work") as operation:
            operations.append(operation)
            plugin.api.events.hook(
                "access:child",
                selected,
                filters=EventFilter(correlation_id=operation.correlation_id),
            )
            receipts.append(await plugin.api.events.emit("access:child", value=2))

    plugin.api.events.hook("access:root", root)
    plugin.api.events.hook("access:child", child)
    scope = (
        app_context.operations.scope("existing")
        if existing_operation
        else nullcontext()
    )
    with scope:
        caller_correlation = current_correlation_id()
        receipt = await plugin.api.events.emit("access:root", value=1)
        assert current_correlation_id() == caller_correlation
    assert not receipt.failures
    assert len(receipts) == 1 and not receipts[0].failures
    assert operations[0].correlation_id == receipt.correlation_id
    assert children == [(receipt.correlation_id, receipt.correlation_id)]
    assert filtered == [receipt.correlation_id]
    assert current_correlation_id() is None


async def test_api_called_from_custom_event_keeps_correlation(
    app_context, plugin_factory, real_bedrock_server
):
    from bedrock_server_manager.events.bus import current_correlation_id

    plugin = await plugin_factory("access", SOURCE)
    plugin.api.events.define("access:launch", ValuePayload)
    seen, responses = [], []

    async def before_start(event):
        seen.append((event.context.correlation_id, event.operation.correlation_id))

    async def launch(event):
        responses.append(
            await plugin.api.server.start(
                {"server_name": real_bedrock_server.server_name}
            )
        )

    plugin.api.events.hook("before_server_start", before_start)
    plugin.api.events.hook("access:launch", launch)
    receipt = await plugin.api.events.emit("access:launch", value=1)
    assert not receipt.failures
    assert len(responses) == 1 and responses[0].outcome == "started"
    assert seen == [(receipt.correlation_id, receipt.correlation_id)]
    assert current_correlation_id() is None
