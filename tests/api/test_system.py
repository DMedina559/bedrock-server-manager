import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetBedrockProcessInfoRequest,
    GetServerRunningStatusRequest,
)
from bedrock_server_manager.api.system import (
    get_bedrock_process_info,
    get_server_running_status,
)


async def test_running_status_follows_real_server_process(
    app_context, real_bedrock_server
):
    request = GetServerRunningStatusRequest(server_name=real_bedrock_server.server_name)
    assert not (
        await get_server_running_status(request, app_context=app_context)
    ).is_running
    await real_bedrock_server.start()
    assert (
        await get_server_running_status(request, app_context=app_context)
    ).is_running
    await real_bedrock_server.stop()
    assert not (
        await get_server_running_status(request, app_context=app_context)
    ).is_running


async def test_stopped_server_has_no_process_info(app_context, real_bedrock_server):
    response = await get_bedrock_process_info(
        GetBedrockProcessInfoRequest(server_name=real_bedrock_server.server_name),
        app_context=app_context,
    )
    assert response.status == "success"
    assert response.process_info is None


@pytest.mark.parametrize(
    "model", [GetBedrockProcessInfoRequest, GetServerRunningStatusRequest]
)
def test_system_requests_require_server_identity(model):
    with pytest.raises(ValidationError):
        model(server_name="")
