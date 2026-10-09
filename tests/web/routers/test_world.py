import shutil
from pathlib import Path

import pytest


async def test_http_world_import_export_and_reset(
    admin_auth_client,
    app_context,
    real_bedrock_server,
    valid_mcworld_zip,
    wait_for_task,
):
    content = Path(app_context.settings.get("paths.content")) / "worlds"
    content.mkdir(parents=True, exist_ok=True)
    destination = content / "integration.mcworld"
    shutil.copy2(valid_mcworld_zip, destination)
    base = f"/api/server/{real_bedrock_server.server_name}/world"
    response = await admin_auth_client.post(
        base + "/install", json={"filename": destination.name}
    )
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])
    world = (
        Path(real_bedrock_server.paths.server_dir)
        / "worlds"
        / await real_bedrock_server.get_world_name()
    )
    assert (world / "level.dat").is_file()
    response = await admin_auth_client.post(base + "/export")
    assert response.status_code == 202
    snapshot = await wait_for_task(app_context, response.json()["task_id"])
    assert Path(snapshot.result["export_file"]).is_file()
    response = await admin_auth_client.request("DELETE", base + "/reset")
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])
    assert not world.exists()


@pytest.mark.parametrize(
    "filename", ["../outside.mcworld", "/outside.mcworld", "missing.mcworld"]
)
async def test_world_import_rejects_unsafe_or_missing_content(
    admin_auth_client, real_bedrock_server, filename
):
    response = await admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/world/install",
        json={"filename": filename},
    )
    assert response.status_code in {400, 404, 422}


async def test_world_changes_require_admin(auth_client, real_bedrock_server):
    assert (
        await auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/world/export"
        )
    ).status_code == 403


async def test_world_icon_is_served_from_actual_world(
    admin_auth_client, populated_server
):
    world = (
        Path(populated_server.paths.server_dir)
        / "worlds"
        / await populated_server.get_world_name()
    )
    icon = world / "world_icon.jpeg"
    icon.write_bytes(b"integration icon")
    response = await admin_auth_client.get(
        f"/api/server/{populated_server.server_name}/world/icon"
    )
    assert response.status_code == 200
    assert response.content == icon.read_bytes()
