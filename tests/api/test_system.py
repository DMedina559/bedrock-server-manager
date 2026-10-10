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


async def test_process_observation_revision_precedes_delayed_read(
    app_context, real_bedrock_server, monkeypatch
):
    import asyncio

    from bedrock_server_manager.api.models.system import GetBedrockProcessInfoRequest
    from bedrock_server_manager.api.system import get_bedrock_process_info
    from bedrock_server_manager.state_revision import revision_clock

    entered = asyncio.Event()
    release = asyncio.Event()

    async def delayed_read():
        entered.set()
        await release.wait()
        return None

    monkeypatch.setattr(real_bedrock_server, "get_process_info", delayed_read)
    pending = asyncio.create_task(
        get_bedrock_process_info(
            GetBedrockProcessInfoRequest(server_name=real_bedrock_server.server_name),
            app_context=app_context,
        )
    )
    try:
        async with asyncio.timeout(5):
            await entered.wait()
        newer = revision_clock.capture()
        release.set()
        result = await pending
        assert result.epoch == newer["epoch"]
        assert result.revision < newer["revision"]
    finally:
        release.set()
        await asyncio.gather(pending, return_exceptions=True)
