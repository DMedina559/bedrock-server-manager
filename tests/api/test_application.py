import shutil
from pathlib import Path

from bedrock_server_manager.api.application import (
    get_all_servers_data,
    get_system_and_app_info,
    list_available_worlds,
    update_server_statuses,
)
from bedrock_server_manager.api.models import (
    GetAllServersDataRequest,
    GetSystemAndAppInfoRequest,
    ListAvailableWorldsRequest,
    UpdateServerStatusesRequest,
)


async def test_application_api_worlds_servers_and_system_info(
    app_context, real_bedrock_server, valid_mcworld_zip
):
    # System info
    sys_info = get_system_and_app_info(
        GetSystemAndAppInfoRequest(), app_context=app_context
    )
    assert sys_info.os_type and sys_info.app_version and sys_info.splash_text

    # Available worlds
    content = Path(app_context.settings.get("paths.content")) / "worlds"
    content.mkdir(parents=True, exist_ok=True)
    archive = content / "integration.mcworld"
    shutil.copyfile(valid_mcworld_zip, archive)
    (content / "ignored.txt").write_text("ignored")
    worlds_resp = await list_available_worlds(
        ListAvailableWorldsRequest(), app_context=app_context
    )
    assert worlds_resp.files == [str(archive)]

    # Server listing and statuses
    response = await get_all_servers_data(
        GetAllServersDataRequest(), app_context=app_context
    )
    assert [server.name for server in response.servers] == [
        real_bedrock_server.server_name
    ]
    await real_bedrock_server.start()
    await __import__("asyncio").wait_for(
        real_bedrock_server.process.run.ready_event.wait(), 5
    )
    result = await update_server_statuses(
        UpdateServerStatusesRequest(), app_context=app_context
    )
    assert result.updated_servers_count == 1 and result.errors == []
    response = await get_all_servers_data(
        GetAllServersDataRequest(), app_context=app_context
    )
    assert response.servers[0].status == "RUNNING"
    await real_bedrock_server.stop()
    await update_server_statuses(UpdateServerStatusesRequest(), app_context=app_context)
    response = await get_all_servers_data(
        GetAllServersDataRequest(), app_context=app_context
    )
    assert response.servers[0].status == "STOPPED"
