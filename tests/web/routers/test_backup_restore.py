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
