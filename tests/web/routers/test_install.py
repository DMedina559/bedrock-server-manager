from pathlib import Path

import pytest


async def test_http_custom_install_completes_and_registers_server(
    admin_auth_client, app_context, dummy_server_zip, wait_for_task
):
    directory = Path(app_context.settings.get("paths.downloads")) / "custom"
    directory.mkdir(parents=True, exist_ok=True)
    archive = dummy_server_zip(target_dir=directory, version="1.26.45.1")
    response = await admin_auth_client.get("/api/downloads/list")
    assert response.status_code == 200
    assert archive.name in response.json()["custom_zips"]
    response = await admin_auth_client.post(
        "/api/server/install",
        json={
            "server_name": "http_installed",
            "server_version": "CUSTOM",
            "server_zip_path": archive.name,
        },
    )
    assert response.status_code == 200
    await wait_for_task(app_context, response.json()["task_id"])
    server = app_context.get_server("http_installed")
    assert await server.is_installed()
    response = await admin_auth_client.get("/api/server/http_installed/summary")
    assert response.status_code == 200
    assert response.json()["name"] == "http_installed"


async def test_download_listing_without_custom_directory(admin_auth_client):
    response = await admin_auth_client.get("/api/downloads/list")
    assert response.status_code == 200
    assert response.json()["custom_zips"] == []


async def test_install_requires_admin(unauth_client, auth_client):
    payload = {"server_name": "installed", "server_version": "LATEST"}
    assert (
        await unauth_client.post("/api/server/install", json=payload)
    ).status_code == 401
    assert (
        await auth_client.post("/api/server/install", json=payload)
    ).status_code == 403


@pytest.mark.parametrize("filename", ["../outside.zip", "/outside.zip"])
async def test_custom_install_rejects_unsafe_paths(admin_auth_client, filename):
    response = await admin_auth_client.post(
        "/api/server/install",
        json={
            "server_name": "installed",
            "server_version": "CUSTOM",
            "server_zip_path": filename,
        },
    )
    assert response.status_code in {400, 422}


async def test_invalid_custom_path_preserves_existing_server(
    admin_auth_client, real_bedrock_server
):
    executable = Path(real_bedrock_server.paths.bedrock_executable_path)
    original = executable.read_bytes()
    response = await admin_auth_client.post(
        "/api/server/install",
        json={
            "server_name": real_bedrock_server.server_name,
            "server_version": "CUSTOM",
            "server_zip_path": "../outside.zip",
            "overwrite": True,
        },
    )
    assert response.status_code == 400
    assert executable.read_bytes() == original


async def test_missing_custom_archive_preserves_existing_server(
    admin_auth_client, real_bedrock_server
):
    executable = Path(real_bedrock_server.paths.bedrock_executable_path)
    original = executable.read_bytes()
    response = await admin_auth_client.post(
        "/api/server/install",
        json={
            "server_name": real_bedrock_server.server_name,
            "server_version": "CUSTOM",
            "server_zip_path": "missing.zip",
            "overwrite": True,
        },
    )
    assert response.status_code == 404
    assert executable.read_bytes() == original


@pytest.mark.parametrize(
    "version,expected", [("LATEST", "1.26.45.1"), ("PREVIEW", "1.26.60.23")]
)
async def test_http_download_install_creates_runnable_persisted_server(
    admin_auth_client, app_context, download_api, wait_for_task, version, expected
):
    name = "downloaded_" + version.lower()
    response = await admin_auth_client.post(
        "/api/server/install", json={"server_name": name, "server_version": version}
    )
    assert response.status_code == 200
    await wait_for_task(app_context, response.json()["task_id"])
    await app_context.reload()
    server = app_context.get_server(name)
    assert await server.is_installed()
    assert await server.get_version() == expected
    response = await admin_auth_client.post(f"/api/server/{name}/start")
    try:
        assert response.status_code == 200
        assert response.json()["outcome"] == "started"
        assert await server.is_running()
        assert server.process._process.returncode is None
    finally:
        await server.stop()
