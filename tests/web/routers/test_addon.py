import shutil
from pathlib import Path

import pytest


async def test_http_addon_install_and_activation(
    admin_auth_client,
    app_context,
    populated_server,
    valid_behavior_pack_zip,
    wait_for_task,
):
    content = Path(app_context.settings.get("paths.content")) / "addons"
    content.mkdir(parents=True, exist_ok=True)
    archive = content / "integration.mcpack"
    shutil.copyfile(valid_behavior_pack_zip, archive)
    available = await admin_auth_client.get("/api/content/addons")
    assert available.status_code == 200
    assert archive.name in available.json()["files"]
    base = f"/api/server/{populated_server.server_name}"
    response = await admin_auth_client.post(
        base + "/addon/install", json={"filename": archive.name}
    )
    assert response.status_code == 202
    await wait_for_task(app_context, response.json()["task_id"])
    response = await admin_auth_client.get(base + "/addons")
    assert response.status_code == 200
    addon = next(
        pack
        for pack in response.json()["addons"]["behavior_packs"]
        if pack["name"] == "Valid BP Zip"
    )
    payload = {"pack_uuid": addon["uuid"], "pack_type": "behavior"}
    for action, expected in [("disable", "INACTIVE"), ("enable", "ACTIVE")]:
        response = await admin_auth_client.post(base + "/addon/" + action, json=payload)
        assert response.status_code == 202
        await wait_for_task(app_context, response.json()["task_id"])
        packs = (await admin_auth_client.get(base + "/addons")).json()["addons"][
            "behavior_packs"
        ]
        assert (
            next(pack for pack in packs if pack["uuid"] == addon["uuid"])["status"]
            == expected
        )


@pytest.mark.parametrize("filename", ["../outside.mcpack", "missing.mcpack"])
async def test_http_addon_rejects_unavailable_archive(
    admin_auth_client, populated_server, filename
):
    response = await admin_auth_client.post(
        f"/api/server/{populated_server.server_name}/addon/install",
        json={"filename": filename},
    )
    assert response.status_code in {400, 404, 422}


async def test_addon_mutations_require_admin(auth_client, populated_server):
    response = await auth_client.post(
        f"/api/server/{populated_server.server_name}/addon/install",
        json={"filename": "integration.mcpack"},
    )
    assert response.status_code == 403


async def test_addon_listing_requires_authentication(unauth_client):
    assert (await unauth_client.get("/api/content/addons")).status_code == 401
