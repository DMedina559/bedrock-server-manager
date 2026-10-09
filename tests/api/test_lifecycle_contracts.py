import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.errors import error_response
from bedrock_server_manager.api.models import (
    RestartServerRequest,
    StartServerRequest,
    StartServerResponse,
)
from bedrock_server_manager.api.server import restart_server, start_server
from bedrock_server_manager.error import (
    APICancelledError,
    ServerStartError,
    ServerStopError,
)
from bedrock_server_manager.plugins.api_bridge import create_app_api


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
async def test_invalid_request_preserves_real_runtime(
    app_context, real_bedrock_server, payload
):
    before = app_context.state.runtime.servers
    with pytest.raises(ValidationError):
        await start_server(payload, app_context=app_context)
    assert app_context.state.runtime.servers == before
    assert not await real_bedrock_server.is_running()


async def test_constructed_invalid_instance_is_revalidated(app_context):
    request = StartServerRequest.model_construct(server_name="../example")
    with pytest.raises(ValidationError):
        await start_server(request, app_context=app_context)
    assert app_context._servers == {}


async def test_real_start_delivers_field_based_plugin_events(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory(
        "observer",
        "from bedrock_server_manager import PluginBase\nclass Observer(PluginBase):\n    version = '1.0'\n",
    )
    before, after = [], []

    async def on_before(**kwargs):
        before.append(kwargs)

    async def on_after(**kwargs):
        after.append(kwargs)

    plugin.api.listen_for_event("before_server_start", on_before)
    plugin.api.listen_for_event("after_server_start", on_after)
    result = await start_server(
        StartServerRequest(server_name=real_bedrock_server.server_name),
        app_context=app_context,
    )
    assert isinstance(result, StartServerResponse)
    assert result.outcome == "started"
    assert before[0]["server_name"] == real_bedrock_server.server_name
    assert isinstance(before[0]["request"], StartServerRequest)
    assert "app_context" not in before[0]
    assert after[0]["result"] == result
    assert (
        app_context.bedrock_process_manager.servers[real_bedrock_server.server_name]
        is real_bedrock_server
    )


async def test_plugin_cancellation_prevents_process_start_and_after_event(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory(
        "cancel",
        "from bedrock_server_manager import PluginBase\nclass Cancel(PluginBase):\n    version = '1.0'\n",
    )
    after = []

    async def cancel(**kwargs):
        kwargs["event"].cancel("Requested cancellation")

    async def on_after(**kwargs):
        after.append(kwargs)

    plugin.api.listen_for_event("before_server_start", cancel)
    plugin.api.listen_for_event("after_server_start", on_after)
    with pytest.raises(APICancelledError):
        await start_server(
            {"server_name": real_bedrock_server.server_name}, app_context=app_context
        )
    assert not await real_bedrock_server.is_running()
    assert after == []


async def test_actual_executable_failure_is_reported(app_context, real_bedrock_server):
    executable = Path(real_bedrock_server.paths.bedrock_executable_path)
    executable.write_bytes(b"invalid executable")
    with pytest.raises(ServerStartError):
        await start_server(
            {"server_name": real_bedrock_server.server_name}, app_context=app_context
        )
    assert not await real_bedrock_server.is_running()


async def test_restart_stop_failure_preserves_actual_child(
    app_context, real_bedrock_server, monkeypatch
):
    await real_bedrock_server.start()
    child = real_bedrock_server.process._process

    async def fail_stop():
        raise ServerStopError("Still running")

    with monkeypatch.context() as fault:
        fault.setattr(real_bedrock_server, "stop", fail_stop)
        with pytest.raises(ServerStopError):
            await restart_server(
                RestartServerRequest(
                    server_name=real_bedrock_server.server_name, send_message=False
                ),
                app_context=app_context,
            )
    assert real_bedrock_server.process._process is child
    assert await real_bedrock_server.is_running()


async def test_bridge_accepts_mapping_and_describes_actual_contract(
    app_context, real_bedrock_server
):
    api = create_app_api("example_plugin", app_context)
    assert list(inspect.signature(api.server.start).parameters) == ["request"]
    result = await api.server.start({"server_name": real_bedrock_server.server_name})
    assert result.outcome == "started"
    metadata = next(
        item for item in api.list_available_apis() if item["name"] == "start_server"
    )
    assert metadata["contract_version"] == 2
    assert metadata["request_schema"]["required"] == ["server_name"]
    assert metadata["request_schema"]["additionalProperties"] is False
    assert metadata["response_model"] == "StartServerResponse"
    assert "app_context" not in json.dumps(metadata["request_schema"])


async def test_bridge_cannot_override_runtime_context(app_context):
    api = create_app_api("example_plugin", app_context)
    with pytest.raises(TypeError, match="injected"):
        await api.server.start({"server_name": "example"}, app_context=app_context)
    assert app_context._servers == {}


def test_errors_do_not_expose_internal_exception_or_invalid_input():
    envelope = error_response(RuntimeError("private database credentials"))
    assert envelope.code == "internal_error"
    assert "credentials" not in envelope.model_dump_json()
    with pytest.raises(ValidationError) as caught:
        StartServerRequest(server_name="example", secret="secret_value")
    envelope = error_response(caught.value)
    assert envelope.code == "validation_error"
    assert "secret_value" not in envelope.model_dump_json()
