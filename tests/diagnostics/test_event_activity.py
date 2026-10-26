"""Global event and operation metadata across independent execution chains."""

import asyncio

import pytest
from pydantic import BaseModel

from bedrock_server_manager.events import (
    EventActivityQuery,
    EventBus,
    EventFilter,
    EventOptions,
)
from bedrock_server_manager.operations import OperationActivityQuery, OperationService

SOURCE = "from bedrock_server_manager import PluginBase\nclass Probe(PluginBase):\n    version = '1.0'\n"


class Payload(BaseModel):
    value: str


async def test_global_operations_include_independent_active_chains_and_bounded_results():
    service = OperationService(history_limit=2)
    ready = asyncio.Queue()
    release = asyncio.Event()

    async def work(server):
        with service.scope("root", server_name=server) as root:
            with service.scope("step", server_name=server) as step:
                ready.put_nowait((root.snapshot, step.snapshot))
                await release.wait()
            assert len(service.results()) == 1

    tasks = [asyncio.create_task(work(name)) for name in ("alpha", "beta")]
    try:
        first, second = await ready.get(), await ready.get()
        assert first[0].sequence_id != second[0].sequence_id
        assert service.current() is None and service.results() == ()
        activity = service.activity()
        assert activity.active_operations == 4 and activity.active_sequences == 2
        assert len(activity.active) == 4
        child = next(
            item
            for item in activity.active
            if item.operation_id == first[1].operation_id
        )
        assert child.parent_operation_id == first[0].operation_id
        assert child.root_operation_id == first[0].operation_id
        selected = service.activity(
            OperationActivityQuery(server_name="alpha", limit=1)
        )
        assert len(selected.active) == 1 and selected.active_truncated
        assert service.activity(
            OperationActivityQuery(operation_id=child.operation_id)
        ).active == [child]
    finally:
        release.set()
        await asyncio.gather(*tasks)
    activity = service.activity()
    assert not activity.active and not activity.active_sequences
    assert (
        len(activity.recent) == 2
        and activity.completed == 4
        and activity.recent_truncated
    )
    assert service.results() == ()
    activity.recent.clear()
    assert len(service.activity().recent) == 2


@pytest.mark.parametrize(
    "error,status", [(ValueError, "failed"), (asyncio.CancelledError, "cancelled")]
)
async def test_global_operation_failures_cleanup_and_keep_final_outcomes(error, status):
    service = OperationService()
    with pytest.raises(error):
        with service.scope("failed"):
            raise error()
    activity = service.activity()
    assert not activity.active and not activity.active_sequences
    assert activity.recent[0].status == status
    assert activity.recent[0].outcome == status
    assert service.current() is None


async def test_event_activity_filters_across_chains_and_survives_disabled_event_history():
    bus = EventBus()
    operations = []
    for server in ("alpha", "beta"):
        with bus.operations.scope("workflow", server_name=server) as operation:
            operations.append(operation.snapshot)
            await bus.emit(
                "sample", {"secret": "PAYLOAD-SECRET"}, source="plugin:probe"
            )
    records = bus.diagnostics().recent
    assert len({item.sequence_id for item in records}) == 2
    selected = bus.diagnostics(
        EventActivityQuery(
            server_name="alpha", operation_name="workflow", source="plugin:probe"
        )
    )
    assert len(selected.recent) == 1
    assert selected.recent[0].operation_id == operations[0].operation_id
    assert selected.recent[0].sequence_id == operations[0].sequence_id
    assert "PAYLOAD-SECRET" not in selected.model_dump_json()
    assert not bus.diagnostics(EventActivityQuery(sequence_id="missing")).recent
    await bus.close()
    without_history = EventBus(EventOptions(history_limit=0))
    with without_history.operations.scope("work"):
        await without_history.emit("sample")
    assert not without_history.diagnostics().recent
    assert without_history.operations.activity().recent[0].name == "work"
    await without_history.close()


async def test_plugins_observe_all_public_events_and_read_global_activity(
    app_context, plugin_factory
):
    plugin = await plugin_factory("probe", SOURCE)
    other = await plugin_factory("other", SOURCE)
    plugin.api.events.define("probe:public", Payload)
    plugin.api.events.define("probe:private", Payload, public=False)
    other.api.events.define("other:private", Payload, public=False)
    seen = []

    async def observer(event):
        seen.append(event.context.name)
        assert not event.can_cancel

    plugin.api.events.observe_all(observer)
    for name in ("probe:public", "probe:private"):
        with plugin.api.operations.scope("probe:work"):
            await plugin.api.events.emit(name, value="PAYLOAD-SECRET")
    with other.api.operations.scope("other:work"):
        await other.api.events.emit("other:private", value="PAYLOAD-SECRET")
    assert seen == ["probe:public", "probe:private"]
    operations = plugin.api.operations.activity()
    assert {item.name for item in operations.recent} >= {"probe:work", "other:work"}
    assert plugin.api.operations.results() == ()
    events = plugin.api.events.activity()
    assert (
        len(
            {
                item.sequence_id
                for item in events.recent
                if item.name.startswith(("probe:", "other:"))
            }
        )
        == 3
    )
    assert "PAYLOAD-SECRET" not in events.model_dump_json()
    app_context.events.remove_owner("plugin:probe")
    for call in (
        plugin.api.events.activity,
        plugin.api.operations.activity,
        lambda: plugin.api.events.observe_all(observer),
    ):
        with pytest.raises(RuntimeError):
            call()


async def test_admin_activity_snapshot_trace_and_report_include_global_metadata(
    app_context, admin_auth_client, auth_client, unauth_client
):
    bus = app_context.events

    async def callback(**kwargs):
        pass

    token = bus.subscribe(
        "sample",
        callback,
        listener_id="application:sample",
        priority=7,
        filters=EventFilter(server_name="alpha"),
        after=("application:missing",),
    )
    with app_context.operations.scope("workflow", server_name="alpha") as root:
        with app_context.operations.scope("step", server_name="alpha"):
            await bus.emit(
                "sample", {"server_name": "alpha", "secret": "PAYLOAD-SECRET"}
            )
            active = await admin_auth_client.get("/api/diagnostics/activity")
            assert active.status_code == 200, active.text
            assert len(active.json()["operations"]["active"]) == 2
    assert (await unauth_client.get("/api/diagnostics/activity")).status_code == 401
    assert (await auth_client.get("/api/diagnostics/activity")).status_code == 403
    response = await admin_auth_client.get(
        "/api/diagnostics/activity", params={"sequence_id": root.snapshot.sequence_id}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["scope"] == "application" and not data["operations"]["active"]
    assert len(data["operations"]["recent"]) == 2
    assert len(data["events"]["recent"]) == 1
    assert data["events"]["recent"][0]["operation_name"] == "step"
    listener = next(
        item
        for item in data["subscriptions"]["items"]
        if item["subscription_id"] == token
    )
    assert listener["priority"] == 7 and listener["calls"] == 1
    assert listener["filters"]["server_name"] == "alpha"
    assert listener["unresolved_after"] == ["application:missing"]
    snapshot = await admin_auth_client.get("/api/diagnostics/events")
    events = next(
        section["data"]
        for section in snapshot.json()["sections"]
        if section["name"] == "events"
    )
    assert events["operations"]["recent"] and events["subscriptions"]["items"]
    trace = await admin_auth_client.get(
        f"/api/diagnostics/trace/{root.snapshot.correlation_id}"
    )
    assert trace.status_code == 200
    assert (
        trace.json()["operations_available"]
        and len(trace.json()["operations"]["recent"]) == 2
    )
    report = await admin_auth_client.get("/api/diagnostics/report")
    assert report.status_code == 200
    assert (
        "PAYLOAD-SECRET" not in response.text + snapshot.text + trace.text + report.text
    )
    for limit in (0, 201):
        assert (
            await admin_auth_client.get(
                "/api/diagnostics/activity", params={"limit": limit}
            )
        ).status_code == 422


async def test_diagnostic_activity_is_bounded_copied_and_isolates_failures(app_context):
    from bedrock_server_manager.diagnostics.models import DiagnosticOptions

    bus = app_context.events
    service = app_context.diagnostics
    service.options = DiagnosticOptions(event_record_limit=1, event_detail_limit=1)

    async def callback(**kwargs):
        pass

    references = ("application:one", "application:two")
    for index in range(2):
        bus.subscribe(
            "sample", callback, listener_id=f"application:{index}", after=references
        )
        with bus.operations.scope("workflow"):
            await bus.emit("sample")
    activity = service.activity()
    assert activity.truncated
    assert (
        len(activity.events.recent)
        == len(activity.operations.recent)
        == len(activity.subscriptions.items)
        == 1
    )
    assert activity.subscriptions.items[0].after == references[:1]
    assert bus.subscriptions("application")[0].after == references

    def broken(query):
        raise RuntimeError("SECRET")

    service.operation_activity_provider = broken
    activity = service.activity()
    assert activity.events is not None and activity.subscriptions is not None
    assert activity.operations is None
    assert [issue.code for issue in activity.issues] == [
        "activity_operations_unavailable"
    ]
    assert "SECRET" not in activity.model_dump_json()


async def test_plugin_diagnostics_activity_contract(app_context, plugin_factory):
    plugin = await plugin_factory("probe", SOURCE)
    with plugin.api.operations.scope("probe:work"):
        await app_context.events.emit("sample")
    result = await plugin.api.diagnostics.get_diagnostic_activity(
        {"operation_name": "probe:work"}
    )
    assert result.scope == "application"
    assert result.operations.recent[0].name == "probe:work"
    assert result.events.recent[0].operation_name == "probe:work"


async def test_operation_provider_detail_limits_apply_to_global_activity_and_traces(
    app_context,
):
    from bedrock_server_manager.diagnostics.models import DiagnosticOptions
    from bedrock_server_manager.operations import OperationActivity

    service = app_context.diagnostics
    service.options = DiagnosticOptions(event_record_limit=1)
    with app_context.operations.scope("sample") as operation:
        pass
    oversized = OperationActivity(recent=[operation.snapshot] * 3)
    service.operation_activity_provider = lambda query: oversized
    activity = service.activity()
    assert len(activity.operations.recent) == 1
    assert activity.operations.recent_truncated and activity.truncated
    trace = await service.trace(operation.snapshot.correlation_id)
    assert len(trace.operations.recent) == 1
    assert trace.operations.recent_truncated and trace.truncated
    assert len(oversized.recent) == 3


async def test_invalid_operation_observation_does_not_hide_correlated_events(
    app_context,
):
    with app_context.operations.scope("sample") as operation:
        await app_context.events.emit("sample")
    service = app_context.diagnostics
    service.operation_activity_provider = lambda query: "invalid observation"
    trace = await service.trace(operation.snapshot.correlation_id)
    assert trace.operations is None and not trace.operations_available
    assert trace.events_available and trace.events.recent[0].name == "sample"
    assert [issue.code for issue in trace.issues] == ["trace_operations_unavailable"]


@pytest.mark.parametrize("limit", [1, 100, 200])
async def test_activity_accepts_url_integer_limits(admin_auth_client, limit):
    response = await admin_auth_client.get(
        "/api/diagnostics/activity",
        params={"limit": limit, "phase": "custom", "status": "completed"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["scope"] == "application"


@pytest.mark.parametrize("limit", ["abc", "1.5", "0", "201"])
async def test_activity_rejects_invalid_url_limits(admin_auth_client, limit):
    response = await admin_auth_client.get(
        "/api/diagnostics/activity", params={"limit": limit}
    )
    assert response.status_code == 422, response.text


def test_plugin_activity_request_keeps_strict_integer_validation():
    from pydantic import ValidationError

    from bedrock_server_manager.api.models.diagnostics import (
        GetDiagnosticActivityRequest,
    )

    with pytest.raises(ValidationError):
        GetDiagnosticActivityRequest.model_validate({"limit": "100"})
