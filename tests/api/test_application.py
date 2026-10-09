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


async def test_available_worlds_are_actual_content_files(
    app_context, valid_mcworld_zip
):
    content = Path(app_context.settings.get("paths.content")) / "worlds"
    content.mkdir(parents=True, exist_ok=True)
    archive = content / "integration.mcworld"
    shutil.copyfile(valid_mcworld_zip, archive)
    (content / "ignored.txt").write_text("ignored")
    response = await list_available_worlds(
        ListAvailableWorldsRequest(), app_context=app_context
    )
    assert response.files == [str(archive)]


async def test_server_listing_and_status_follow_actual_lifecycle(
    app_context, real_bedrock_server
):
    response = await get_all_servers_data(
        GetAllServersDataRequest(), app_context=app_context
    )
    assert [server.name for server in response.servers] == [
        real_bedrock_server.server_name
    ]
    await real_bedrock_server.start()
    result = await update_server_statuses(
        UpdateServerStatusesRequest(), app_context=app_context
    )
    assert result.updated_servers_count == 1
    assert result.errors == []
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


async def test_system_info_reports_real_application(app_context):
    response = get_system_and_app_info(
        GetSystemAndAppInfoRequest(), app_context=app_context
    )
    assert response.os_type
    assert response.app_version
    assert response.splash_text
