import asyncio

from bedrock_server_manager.api.models import GetBedrockProcessInfoRequest
from bedrock_server_manager.api.system import get_bedrock_process_info
from bedrock_server_manager.state.revision import revision_clock


async def test_stopped_process_info_and_observation_revision(
    app_context, real_bedrock_server, monkeypatch
):
    name = real_bedrock_server.server_name
    # Stopped server has no process info
    proc_resp = await get_bedrock_process_info(
        GetBedrockProcessInfoRequest(server_name=name),
        app_context=app_context,
    )
    assert proc_resp.status == "success" and proc_resp.process_info is None

    # Process observation revision precedes delayed read
    entered = asyncio.Event()
    release = asyncio.Event()

    async def delayed_read():
        entered.set()
        await release.wait()
        return None

    monkeypatch.setattr(real_bedrock_server, "get_process_info", delayed_read)
    pending = asyncio.create_task(
        get_bedrock_process_info(
            GetBedrockProcessInfoRequest(server_name=name),
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
