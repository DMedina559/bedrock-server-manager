"""Diagnostic evidence and managed progress must not retain request payloads."""

import asyncio
import logging
import threading
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.backups.server import inventory
from bedrock_server_manager.contracts import DataContract
from bedrock_server_manager.logging import ApplicationFormatter, _TransportFilter
from bedrock_server_manager.plugins.api_contract import validate_contract
from bedrock_server_manager.utils.progress import report_stage
from bedrock_server_manager.web.tasks import TaskManager


class SensitiveRequest(DataContract):
    secret: int


class EmptyResult(DataContract):
    pass


async def test_managed_stages_and_percentages_are_delivered_and_isolated():
    connection = AsyncMock()
    manager = TaskManager(connection)
    entered, release = asyncio.Event(), asyncio.Event()

    async def operation():
        await report_stage("Building backup inventory")
        manager.report_progress(25)
        entered.set()
        await release.wait()
        return EmptyResult()

    identifier = await manager.run_task(operation, "admin")
    try:
        async with asyncio.timeout(3):
            await entered.wait()
        while manager._background_tasks:
            updates = list(manager._background_tasks)
            await asyncio.gather(*updates)
            manager._background_tasks.difference_update(updates)
        snapshot = await manager.get_task(identifier)
        assert snapshot.message == "Building backup inventory (25%)"
        assert manager.diagnostic_snapshot().tasks[0].progress_percent == 25
        deliveries = [
            call.args[1]["data"] for call in connection.send_to_user.call_args_list
        ]
        assert any(item["message"].endswith("(25%)") for item in deliveries)
        await report_stage("Unrelated caller")
        assert (await manager.get_task(identifier)).message == snapshot.message
    finally:
        release.set()
        await manager.shutdown()
    assert manager.diagnostic_snapshot().tasks[0].progress_percent == 100


async def test_async_api_failure_logs_traceback_without_request_dump(caplog):
    @validate_contract
    async def operation(request: SensitiveRequest) -> EmptyResult:
        raise RuntimeError("worker failure")

    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError):
        await operation(SensitiveRequest(secret=918273645))
    assert "918273645" not in caplog.text
    failures = [record for record in caplog.records if record.exc_info]
    assert len(failures) == 1
    assert "API operation failed" in failures[0].getMessage()
    assert "finished: failed" in caplog.text


def test_validation_traceback_hides_supplied_value():
    try:
        SensitiveRequest.model_validate({"secret": "private-input-918273"})
    except ValidationError as error:
        record = logging.LogRecord(
            "test", logging.ERROR, "", 1, "Invalid input", (), None
        )
        record.exc_info = (type(error), error, error.__traceback__)
        formatted = ApplicationFormatter("%(message)s").format(record)
        assert "private-input-918273" not in formatted
        assert "secret" in formatted
    else:
        pytest.fail("Expected validation failure")


def test_protocol_frame_payloads_are_not_logged():
    record = logging.LogRecord(
        "uvicorn.error",
        logging.DEBUG,
        "",
        1,
        "< TEXT %s",
        ("private client data",),
        None,
    )
    assert not _TransportFilter().filter(record)


def test_inventory_cancellation_is_cooperative(tmp_path):
    world = tmp_path / "world"
    world.mkdir()
    (world / "level.dat").write_bytes(b"world")
    cancellation = threading.Event()
    cancellation.set()
    with pytest.raises(InterruptedError):
        inventory(tmp_path, {"world": "included"}, cancellation)


@pytest.mark.parametrize("purpose", ["manual", "pre_start"])
async def test_backup_stages_reach_managed_context_without_explicit_callback(
    populated_server, purpose, caplog
):
    from bedrock_server_manager.utils.progress import progress_scope

    stages = []

    async def capture(message):
        stages.append(message)

    with caplog.at_level(logging.DEBUG), progress_scope(capture):
        result = await populated_server.backups.create_snapshot(
            mode="world", purpose=purpose
        )
    assert result.manifest.mode == "world"
    assert "Capturing server files" in stages
    assert "Building backup inventory" in stages
    assert "Compressing backup" in stages
    assert "Backup inventory complete: files=" in caplog.text
    assert "Backup capture completed" in caplog.text


async def test_cancelled_backup_logs_last_stage(populated_server, monkeypatch, caplog):
    async def stalled(**kwargs):
        await kwargs["progress"]("Building backup inventory")
        await asyncio.Event().wait()

    monkeypatch.setattr(populated_server.backups, "_create_snapshot", stalled)
    with caplog.at_level(logging.WARNING), pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await populated_server.backups.create_snapshot(
                mode="world", purpose="pre_start"
            )
    assert "cancelled during 'Building backup inventory'" in caplog.text


async def test_listener_failure_retains_traceback_and_event_identity(caplog):
    from bedrock_server_manager.events import EventBus

    bus = EventBus()

    async def broken(**kwargs):
        raise RuntimeError("listener failure")

    bus.subscribe("sample", broken)
    with caplog.at_level(logging.DEBUG):
        await bus.emit("sample", {"secret": "DO-NOT-LOG-PAYLOAD"})
    records = [
        r
        for r in caplog.records
        if "Event listener 'application' failed" in r.getMessage()
    ]
    assert len(records) == 1 and records[0].exc_info
    assert "event_id=" in records[0].getMessage()
    assert "deadline_seconds=" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "DO-NOT-LOG-PAYLOAD" not in caplog.text


async def test_plugin_stage_is_owner_checked():
    from bedrock_server_manager.error import UserInputError

    manager = TaskManager(None)
    entered, release = asyncio.Event(), asyncio.Event()

    async def operation():
        with pytest.raises(UserInputError):
            await manager.report_plugin_stage("Wrong owner", plugin_owner="other")
        with pytest.raises(UserInputError):
            await manager.report_plugin_stage("", plugin_owner="probe")
        await manager.report_plugin_stage("Checking files", plugin_owner="probe")
        entered.set()
        await release.wait()

    identifier = await manager.run_task(operation, _plugin_owner="probe")
    try:
        async with asyncio.timeout(3):
            await entered.wait()
        assert (await manager.get_task(identifier)).message == "Checking files"
    finally:
        release.set()
        await manager.shutdown()
