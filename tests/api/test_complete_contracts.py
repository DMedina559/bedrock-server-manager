"""Prevent partial migrations and runtime objects in public data contracts."""

import importlib
import inspect
import json
import pkgutil
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager import api
from bedrock_server_manager.api.models import APIRequest, APIResponse
from bedrock_server_manager.api.models.settings import SetGlobalSettingRequest
from bedrock_server_manager.api.models.web import CreateWebUiServiceRequest
from bedrock_server_manager.plugins.api_bridge import create_app_api
from bedrock_server_manager.plugins.api_contract import get_contract


def operations():
    for info in pkgutil.iter_modules(api.__path__):
        if info.ispkg or info.name == "errors":
            continue
        module = importlib.import_module(f"{api.__name__}.{info.name}")
        for name, operation in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("_") or operation.__module__ != module.__name__:
                continue
            yield f"{info.name}.{name}", operation


def test_every_data_operation_has_complete_serializable_contract():
    found = list(operations())
    assert len(found) == 80
    for name, operation in found:
        request, response = get_contract(operation)
        assert issubclass(request, APIRequest), name
        assert issubclass(response, APIResponse), name
        signature = inspect.signature(operation)
        if "app_context" in signature.parameters:
            assert (
                signature.parameters["app_context"].kind
                is inspect.Parameter.KEYWORD_ONLY
            )
        for model, mode in ((request, "validation"), (response, "serialization")):
            schema = model.model_json_schema(mode=mode)
            json.dumps(schema)
            assert schema["additionalProperties"] is False, name
            assert not (
                {"app_context", "plugin_name"} & model.model_fields.keys()
            ), name


def test_all_registered_data_apis_expose_version_two_contracts():
    api_instance = create_app_api("core", None, is_core=True)
    metadata = api_instance.list_available_apis(include_internal=True)
    assert len(metadata) == 61
    assert all(item["contract_version"] == 2 for item in metadata)
    assert all(item["request_schema"] and item["response_schema"] for item in metadata)
    assert not {
        "run_task",
        "server_lifecycle_manager",
        "websocket_register_data_provider",
    } & {item["name"] for item in metadata}
    json.dumps(
        [
            {key: value for key, value in item.items() if key.endswith("schema")}
            for item in metadata
        ]
    )


@pytest.mark.parametrize("operation_name, operation", list(operations()))
async def test_unknown_fields_fail_before_runtime_access(operation_name, operation):
    context = MagicMock()
    with pytest.raises(ValidationError):
        runtime = (
            {"app_context": context}
            if "app_context" in inspect.signature(operation).parameters
            else {}
        )
        if "plugin_name" in inspect.signature(operation).parameters:
            runtime["plugin_name"] = "test_plugin"
        result = operation({"unexpected_field": True}, **runtime)
        if inspect.isawaitable(result):
            await result
    assert context.mock_calls == [], operation_name


def test_config_values_reject_non_json_runtime_objects():
    with pytest.raises(ValidationError):
        SetGlobalSettingRequest(key="runtime", value=lambda: None)
    with pytest.raises(ValidationError):
        SetGlobalSettingRequest(key="runtime", value=object())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("nested", [False, True])
def test_json_contracts_reject_non_finite_numbers(value, nested):
    from bedrock_server_manager.api.models.settings import GetGlobalSettingResponse

    payload = {"items": [value]} if nested else value
    for model, data in (
        (SetGlobalSettingRequest, {"key": "example", "value": payload}),
        (GetGlobalSettingResponse, {"value": payload}),
    ):
        with pytest.raises(ValidationError):
            model.model_validate(data)


@pytest.mark.parametrize("base", [APIRequest, APIResponse])
def test_contract_defaults_are_validated(base):
    class InvalidDefault(base):
        count: int = "1"  # type: ignore[assignment]

    with pytest.raises(ValidationError):
        InvalidDefault()


def test_json_contract_round_trip_preserves_scalar_types():
    payload = {"items": [None, True, 1, 1.5, "1", {"nested": False}]}
    request = SetGlobalSettingRequest(key="example", value=payload)
    restored = SetGlobalSettingRequest.model_validate_json(request.model_dump_json())
    assert restored == request
    assert type(restored.value["items"][1]) is bool
    assert type(restored.value["items"][2]) is int


def test_service_password_never_serializes():
    request = CreateWebUiServiceRequest.model_validate({"password": "private-password"})
    assert request.password.get_secret_value() == "private-password"
    assert "private-password" not in repr(request)
    assert "password" not in request.model_dump(mode="json")


async def test_runtime_task_preserves_positional_arguments_and_trusted_context():
    context = MagicMock()
    context.task_manager.run_task = AsyncMock(return_value="task-1")
    api_instance = create_app_api("trusted", context)

    def task(value):
        return value

    assert await api_instance.runtime.run_task(task, 42, username="admin") == "task-1"
    context.task_manager.run_task.assert_awaited_once_with(
        task, "admin", 42, _plugin_owner="trusted"
    )
    with pytest.raises(TypeError, match="injected"):
        await api_instance.runtime.run_task(task, app_context=MagicMock())
    with pytest.raises(TypeError, match="injected"):
        await api_instance.runtime.run_task(task, plugin_name="other")
    with pytest.raises(TypeError, match="injected"):
        await api_instance.runtime.run_task(task, _plugin_owner="other")


async def test_runtime_provider_registration_failure_propagates():
    context = MagicMock()
    context.connection_manager.register_data_provider.side_effect = RuntimeError(
        "provider failed"
    )
    api_instance = create_app_api("trusted", context)
    with pytest.raises(RuntimeError, match="provider failed"):
        await api_instance.runtime.register_data_provider("topic", lambda value: value)


@pytest.mark.parametrize("bad_count", [True, "3", -1])
def test_numeric_request_fields_do_not_coerce_invalid_values(bad_count):
    from bedrock_server_manager.api.models import UpdateServerPlayerStatsRequest

    with pytest.raises(ValidationError):
        UpdateServerPlayerStatsRequest.model_validate(
            {"server_name": "example", "player_count": bad_count, "players": []}
        )


def test_success_data_requirements_are_reflected_in_schema():
    from bedrock_server_manager.api.models import ExportWorldResponse

    assert ExportWorldResponse(status="skipped", message="Busy").export_file is None
    with pytest.raises(ValidationError):
        ExportWorldResponse(status="success", message="Exported")
    schema = ExportWorldResponse.model_json_schema(mode="serialization")
    assert schema["allOf"][0]["then"]["required"] == ["export_file"]


async def test_plugin_target_event_retains_listener_fields_and_identity():
    from bedrock_server_manager.api.models import SetPluginStatusRequest
    from bedrock_server_manager.api.plugins import set_plugin_status
    from bedrock_server_manager.plugins.event_trigger import _event_registry

    context = MagicMock()
    context.connection_manager.broadcast_to_topic = AsyncMock()
    manager = context.plugin_manager
    manager.trigger_event = AsyncMock()
    manager._synchronize_config_with_disk = AsyncMock()
    manager.enable_plugin = AsyncMock()
    manager.plugin_config = {"target": {"enabled": False}}
    await set_plugin_status(
        SetPluginStatusRequest(target_plugin_name="target", enabled=True),
        app_context=context,
    )
    before = manager.trigger_event.call_args_list[0]
    assert before.args == ("before_set_plugin_status",)
    assert before.kwargs["plugin_name"] == "target"
    assert before.kwargs["enabled"] is True
    assert "target_plugin_name" not in before.kwargs
    assert _event_registry["before_set_plugin_status"] == ("plugin_name", "enabled")
