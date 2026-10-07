"""Behavioral regression coverage for model validation and lifecycle effects."""

import inspect
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.errors import error_response
from bedrock_server_manager.api.models import (
    RestartServerRequest,
    StartServerRequest,
    StartServerResponse,
    StopServerRequest,
)
from bedrock_server_manager.api.server import restart_server, start_server, stop_server
from bedrock_server_manager.error import (
    APICancelledError,
    ServerStartError,
    ServerStopError,
)
from bedrock_server_manager.plugins.api_bridge import create_app_api


@pytest.fixture
def lifecycle_context():
    context = MagicMock()
    server = MagicMock()
    server.server_name = "example"
    server.is_running = AsyncMock(return_value=False)
    server.start = AsyncMock()
    server.stop = AsyncMock()
    server.send_command = AsyncMock()
    server.set_status_in_config = AsyncMock()
    server.get_pid_file_path.return_value = "/nonexistent/example.pid"
    context.get_server.return_value = server
    context.plugin_manager.trigger_event = AsyncMock()
    context.connection_manager.broadcast_to_topic = AsyncMock()
    context.bedrock_process_manager.add_server = AsyncMock()
    context.bedrock_process_manager.remove_server = AsyncMock()
    context.api.set_server_status = AsyncMock()
    return context


@pytest.mark.parametrize(
    "payload",
    [
        {"server_name": ""},
        {"server_name": " "},
        {"server_name": "../example"},
        {"server_name": "example\n"},
        {"server_name": 12},
        {"server_name": "example", "typo": True},
    ],
)
async def test_invalid_request_has_no_events_or_side_effects(
    lifecycle_context, payload
):
    with pytest.raises(ValidationError):
        await start_server(payload, app_context=lifecycle_context)
    lifecycle_context.get_server.assert_not_called()
    lifecycle_context.plugin_manager.trigger_event.assert_not_awaited()


async def test_constructed_invalid_instance_is_revalidated(lifecycle_context):
    request = StartServerRequest.model_construct(server_name="../example")
    with pytest.raises(ValidationError):
        await start_server(request, app_context=lifecycle_context)
    lifecycle_context.get_server.assert_not_called()


async def test_start_has_typed_result_and_field_based_events(lifecycle_context):
    result = await start_server(
        StartServerRequest(server_name="example"), app_context=lifecycle_context
    )
    assert isinstance(result, StartServerResponse)
    assert result.outcome == "started"
    lifecycle_context.bedrock_process_manager.add_server.assert_awaited_once_with(
        lifecycle_context.get_server.return_value
    )
    before, after = lifecycle_context.plugin_manager.trigger_event.await_args_list
    assert before.args == ("before_server_start",)
    assert before.kwargs["server_name"] == "example"
    assert "request" not in before.kwargs and "app_context" not in before.kwargs
    assert after.kwargs["result"] == result.model_dump(mode="json")
    json.dumps(
        lifecycle_context.connection_manager.broadcast_to_topic.await_args.args[1]
    )


@pytest.mark.parametrize(
    "operation,payload,outcome",
    [
        (start_server, StartServerRequest(server_name="example"), "already_running"),
        (stop_server, StopServerRequest(server_name="example"), "already_stopped"),
    ],
)
async def test_idempotent_lifecycle_outcome(
    lifecycle_context, operation, payload, outcome
):
    server = lifecycle_context.get_server.return_value
    server.is_running.return_value = operation is start_server
    result = await operation(payload, app_context=lifecycle_context)
    assert result.status == "success" and result.outcome == outcome
    server.start.assert_not_awaited()
    server.stop.assert_not_awaited()


async def test_cancellation_prevents_start_and_after_event(lifecycle_context):
    async def cancel(name, **kwargs):
        kwargs["event"].cancel("Requested cancellation")

    lifecycle_context.plugin_manager.trigger_event.side_effect = cancel
    with pytest.raises(APICancelledError):
        await start_server({"server_name": "example"}, app_context=lifecycle_context)
    lifecycle_context.get_server.assert_not_called()
    assert lifecycle_context.plugin_manager.trigger_event.await_count == 1


async def test_start_failure_propagates_original_exception(lifecycle_context):
    error = ServerStartError("Failed start")
    lifecycle_context.get_server.return_value.start.side_effect = error
    with pytest.raises(ServerStartError) as caught:
        await start_server({"server_name": "example"}, app_context=lifecycle_context)
    assert caught.value is error
    lifecycle_context.bedrock_process_manager.add_server.assert_not_awaited()
    assert lifecycle_context.plugin_manager.trigger_event.await_count == 1


async def test_restart_aborts_when_stop_fails_and_keeps_pid(
    lifecycle_context, monkeypatch
):
    server = lifecycle_context.get_server.return_value
    server.is_running.return_value = True
    server.stop.side_effect = ServerStopError("Still running")
    cleanup = AsyncMock()
    monkeypatch.setattr(
        "bedrock_server_manager.api.server.remove_pid_file_if_exists", cleanup
    )
    with pytest.raises(ServerStopError):
        await restart_server(
            RestartServerRequest(server_name="example", send_message=False),
            app_context=lifecycle_context,
        )
    server.start.assert_not_awaited()
    server.send_command.assert_not_awaited()
    lifecycle_context.bedrock_process_manager.remove_server.assert_not_awaited()
    cleanup.assert_not_awaited()


async def test_restart_sequences_stop_start_and_monitoring(lifecycle_context):
    server = lifecycle_context.get_server.return_value
    server.is_running.side_effect = [True, True, False]
    result = await restart_server(
        RestartServerRequest(server_name="example"), app_context=lifecycle_context
    )
    assert result.outcome == "restarted"
    server.send_command.assert_awaited_once_with("say Restarting server...")
    server.stop.assert_awaited_once()
    server.start.assert_awaited_once()
    lifecycle_context.bedrock_process_manager.remove_server.assert_awaited_once_with(
        "example"
    )
    lifecycle_context.bedrock_process_manager.add_server.assert_awaited_once_with(
        server
    )


async def test_bridge_accepts_one_mapping_and_exposes_contract(lifecycle_context):
    api = create_app_api("example_plugin", lifecycle_context)
    assert list(inspect.signature(api.start_server).parameters) == ["request"]
    result = await api.servers.start_server({"server_name": "example"})
    assert result.outcome == "started"
    metadata = next(
        item for item in api.list_available_apis() if item["name"] == "start_server"
    )
    assert metadata["contract_version"] == 2
    assert metadata["request_schema"]["required"] == ["server_name"]
    assert metadata["request_schema"]["additionalProperties"] is False
    assert metadata["response_model"] == "StartServerResponse"
    assert "app_context" not in json.dumps(metadata["request_schema"])
    assert "set_server_status" not in {
        item["name"] for item in api.list_available_apis(include_internal=True)
    }


async def test_bridge_cannot_override_runtime_context(lifecycle_context):
    api = create_app_api("example_plugin", lifecycle_context)
    with pytest.raises(TypeError, match="injected"):
        await api.start_server({"server_name": "example"}, app_context=MagicMock())
    lifecycle_context.get_server.assert_not_called()


def test_errors_do_not_expose_internal_exception_or_invalid_input():
    assert (
        error_response(RuntimeError("private database credentials")).code
        == "internal_error"
    )
    assert (
        "credentials"
        not in error_response(RuntimeError("credentials")).model_dump_json()
    )
    with pytest.raises(ValidationError) as caught:
        StartServerRequest(server_name="example", secret="secret_value")
    envelope = error_response(caught.value)
    assert envelope.code == "validation_error"
    assert "secret_value" not in envelope.model_dump_json()
