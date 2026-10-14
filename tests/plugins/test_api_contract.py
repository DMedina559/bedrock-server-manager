"""Contract registration, sync/async validation, and trusted identity injection."""

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import APIRequest, APIResponse
from bedrock_server_manager.plugins.api_bridge import (
    _api_registry,
    api_method,
    create_app_api,
)
from bedrock_server_manager.plugins.api_contract import APIResponseValidationError
from bedrock_server_manager.plugins.event_trigger import trigger_event


class ExampleRequest(APIRequest):
    value: int


class ExampleResponse(APIResponse):
    doubled: int


@pytest.fixture(autouse=True)
def restore_registry():
    original = _api_registry.copy()
    yield
    _api_registry.clear()
    _api_registry.update(original)


def register(func, name="contract_test", exposed=True):
    func.__module__ = "bedrock_server_manager.api.server"
    return api_method(name, expose_to_plugins=exposed)(func)


def test_sync_forward_annotations_validate_and_reflect(app_context):
    def target(request: "ExampleRequest", *, app_context) -> "ExampleResponse":
        return ExampleResponse(doubled=request.value * 2)

    target = register(target)
    api = create_app_api("example", app_context)
    result = api.server.contract_test({"value": 4})
    assert isinstance(result, ExampleResponse) and result.doubled == 8
    assert target.__name__ == "target"
    metadata = next(
        item for item in api.list_available_apis() if item["name"] == "contract_test"
    )
    assert metadata["request_model"] == "ExampleRequest"
    assert metadata["response_schema"]["required"] == ["doubled"]
    assert metadata["is_async"] is False


def test_sync_input_validation_precedes_execution():
    effects = []

    def target(request: ExampleRequest) -> ExampleResponse:
        effects.append(request)
        return ExampleResponse(doubled=request.value * 2)

    target = register(target)
    with pytest.raises(ValidationError):
        target({"value": 2, "misspelled": 4})
    assert effects == []


@pytest.mark.parametrize("construct", [False, True])
def test_invalid_output_is_an_internal_error(construct):
    def target(request: ExampleRequest) -> ExampleResponse:
        if construct:
            # Deliberately simulate an implementation producing invalid output.
            return ExampleResponse(doubled="not an integer")  # type: ignore[arg-type]
        return {"doubled": "not an integer"}  # type: ignore[return-value]

    target = register(target)
    with pytest.raises(APIResponseValidationError):
        target({"value": 2})


async def test_injected_identity_cannot_be_replaced(app_context):
    context = app_context

    async def target(
        request: ExampleRequest, app_context, plugin_name: str
    ) -> ExampleResponse:
        assert app_context is context and plugin_name == "trusted_plugin"
        return ExampleResponse(doubled=request.value * 2)

    register(target)
    api = create_app_api("trusted_plugin", context)
    assert (await api.server.contract_test({"value": 2})).doubled == 4
    with pytest.raises(TypeError, match="injected"):
        await api.server.contract_test({"value": 2}, plugin_name="other_plugin")
    with pytest.raises(TypeError, match="injected"):
        await api.server.contract_test({"value": 2}, context, "other_plugin")


def test_internal_contract_not_discoverable_or_callable_by_plugin():
    def target(request: ExampleRequest) -> ExampleResponse:
        return ExampleResponse(doubled=request.value * 2)

    register(target, exposed=False)
    plugin = create_app_api("untrusted", None)
    assert "contract_test" not in {
        item["name"] for item in plugin.list_available_apis(include_internal=True)
    }
    with pytest.raises(AttributeError):
        plugin.contract_test({"value": 2})
    core = create_app_api("core", None, is_core=True)
    assert core.server.contract_test({"value": 2}).doubled == 4


def test_partial_contract_registration_fails():
    def target(request: ExampleRequest) -> dict:
        return {}

    with pytest.raises(TypeError, match="model annotations"):
        register(target)


def test_extra_scalar_parameters_are_rejected():
    def target(request: ExampleRequest, extra: int) -> ExampleResponse:
        return ExampleResponse(doubled=extra)

    with pytest.raises(TypeError, match="single request"):
        register(target)


async def test_invalid_output_is_not_published_in_after_event(
    app_context, plugin_factory
):
    plugin = await plugin_factory(
        "contract_observer",
        """
from bedrock_server_manager.plugins import PluginBase, app_event
class Observer(PluginBase):
    version = "1.0.0"
    def on_load(self):
        self.events = []
    @app_event("contract_before")
    async def before(self, **kwargs):
        self.events.append("before")
    @app_event("contract_after")
    async def after(self, **kwargs):
        self.events.append("after")
""",
    )

    @trigger_event(before="contract_before", after="contract_after")
    async def target(request: ExampleRequest, app_context) -> ExampleResponse:
        return {"doubled": "invalid"}  # type: ignore[return-value]

    target = register(target)
    with pytest.raises(APIResponseValidationError):
        await target({"value": 2}, app_context=app_context)
    assert plugin.events == ["before"]
