import zipfile
from pathlib import Path

import pytest


async def test_http_config_backup_restore_completes_real_tasks(
    admin_auth_client, app_context, populated_server, wait_for_task
):
    base = f"/api/server/{populated_server.server_name}"
    properties = Path(populated_server.server_dir) / "server.properties"
    original = properties.read_bytes()
    response = await admin_auth_client.post(
        base + "/backup/action",
        json={"backup_type": "config", "file_to_backup": "server.properties"},
    )
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])
    backups = (await admin_auth_client.get(base + "/backup/list/properties")).json()[
        "backups"
    ]
    assert backups
    properties.write_text("server-name=changed\n")
    response = await admin_auth_client.post(
        base + "/restore/action",
        json={"restore_type": "properties", "backup_file": backups[0]},
    )
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])
    assert properties.read_bytes() == original


@pytest.mark.parametrize("kind", ["world", "all"])
async def test_http_backups_create_real_archives(
    admin_auth_client, app_context, populated_server, wait_for_task, kind
):
    base = f"/api/server/{populated_server.server_name}"
    response = await admin_auth_client.post(
        base + "/backup/action", json={"backup_type": kind}
    )
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])
    assert list(Path(populated_server.server_backup_directory).glob("*.mcworld"))
    response = await admin_auth_client.put(base + "/backups/prune")
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])


@pytest.mark.parametrize(
    "filename", ["../outside.properties", "/outside.properties", "missing.properties"]
)
async def test_restore_rejects_unsafe_or_missing_files(
    admin_auth_client, real_bedrock_server, filename
):
    response = await admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/restore/action",
        json={"restore_type": "properties", "backup_file": filename},
    )
    assert response.status_code in {400, 404, 422}


async def test_backups_require_admin(auth_client, real_bedrock_server):
    response = await auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/backup/action",
        json={"backup_type": "all"},
    )
    assert response.status_code == 403


async def test_world_backup_restores_running_server_and_restarts(
    admin_auth_client, app_context, populated_server, wait_for_task
):
    server = populated_server
    base = f"/api/server/{server.server_name}"
    world = Path(server.server_dir) / "worlds" / await server.get_world_name()
    marker = world / "integration.txt"
    marker.write_text("original world")
    pack_files = {
        path.relative_to(world).as_posix(): path.read_bytes()
        for path in world.rglob("manifest.json")
    }
    assert pack_files
    response = await admin_auth_client.post(
        base + "/backup/action", json={"backup_type": "world"}
    )
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])
    archive = next(Path(server.server_backup_directory).glob("*.mcworld"))
    with zipfile.ZipFile(archive) as backup:
        assert backup.read("integration.txt") == b"original world"
        for name, content in pack_files.items():
            assert backup.read(name) == content
    assert (await admin_auth_client.post(base + "/start")).status_code == 200
    first_child = server._process
    assert await server.is_running()
    marker.write_text("changed world")
    for name in pack_files:
        (world / name).unlink()
    response = await admin_auth_client.post(
        base + "/restore/action",
        json={"restore_type": "world", "backup_file": archive.name},
    )
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])
    assert marker.read_text() == "original world"
    for name, content in pack_files.items():
        assert (world / name).read_bytes() == content
    assert first_child.returncode is not None
    assert await server.is_running()
    assert server._process.pid != first_child.pid
    response = await admin_auth_client.post(
        base + "/restart", json={"send_message": False}
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "restarted"
    assert marker.read_text() == "original world"
