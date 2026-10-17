"""Verify local readiness before user setup and capability separation."""

import os

import pytest
from httpx2 import ASGITransport, AsyncClient

from bedrock_server_manager.config import get_installed_version
from bedrock_server_manager.web.control import ControlFiles
from bedrock_server_manager.web.main import create_server
from bedrock_server_manager.web.process import WebProcessPaths, read_control
from bedrock_server_manager.web.runtime import WebRunOptions, WebRuntime


def attach_runtime(app_context, test_app):
    runtime = WebRuntime()
    server = create_server(app_context, WebRunOptions(), runtime)
    test_app.state.web_runtime = runtime
    runtime.ready()
    return runtime, server


async def test_local_readiness_works_before_first_user(
    app_context, test_app, unauth_client
):
    runtime, server = attach_runtime(app_context, test_app)
    assert await app_context.check_setup()
    response = await unauth_client.get(
        "/api/runtime/readiness",
        headers={"X-BSM-Readiness-Token": runtime._readiness_token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"]["instance_id"] == runtime.instance_id
    assert payload["runtime"]["pid"] == os.getpid()
    assert payload["runtime"]["phase"] == "ready"
    assert payload["version"] == get_installed_version()
    assert payload["health"]["ready"] is True
    assert {"lifecycle", "database", "state"} <= payload["health"]["checks"].keys()
    assert not server.should_exit
    assert runtime._readiness_token not in response.text
    assert runtime._token not in response.text


async def test_readiness_capability_cannot_shutdown_or_access_user_api(
    app_context, test_app, unauth_client
):
    runtime, server = attach_runtime(app_context, test_app)
    for headers in (
        {"X-BSM-Readiness-Token": runtime._readiness_token},
        {"X-BSM-Shutdown-Token": runtime._readiness_token},
        {"Authorization": "Bearer " + runtime._readiness_token},
    ):
        response = await unauth_client.post(
            "/api/runtime/shutdown", json={}, headers=headers
        )
        assert response.status_code == 401
        assert (
            await unauth_client.get("/api/runtime", headers=headers)
        ).status_code == 401
        assert (
            await unauth_client.get("/api/health", headers=headers)
        ).status_code == 401
    assert not server.should_exit


@pytest.mark.parametrize("credential", [None, "invalid", "shutdown", "previous"])
async def test_readiness_rejects_missing_invalid_and_other_capabilities(
    app_context, test_app, unauth_client, credential
):
    runtime, _ = attach_runtime(app_context, test_app)
    values = {
        "shutdown": runtime._token,
        "previous": WebRuntime()._readiness_token,
    }
    headers = (
        {}
        if credential is None
        else {"X-BSM-Readiness-Token": values.get(credential, credential)}
    )
    response = await unauth_client.get("/api/runtime/readiness", headers=headers)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("peer", "forwarded"),
    [
        ("203.0.113.10", None),
        ("203.0.113.10", "127.0.0.1"),
        ("127.0.0.1", "203.0.113.10"),
    ],
)
async def test_remote_or_forwarded_remote_clients_cannot_use_local_readiness(
    app_context, test_app, running_app, peer, forwarded
):
    runtime, _ = attach_runtime(app_context, test_app)
    headers = {"X-BSM-Readiness-Token": runtime._readiness_token}
    if forwarded:
        headers["X-Forwarded-For"] = forwarded
    async with AsyncClient(
        transport=ASGITransport(app=running_app, client=(peer, 12345)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/runtime/readiness", headers=headers)
    assert response.status_code == 403


async def test_unmanaged_host_has_no_local_readiness(unauth_client):
    response = await unauth_client.get(
        "/api/runtime/readiness", headers={"X-BSM-Readiness-Token": "invalid"}
    )
    assert response.status_code == 503


async def test_stopping_runtime_is_reported_without_claiming_ready(
    app_context, test_app, unauth_client
):
    runtime, _ = attach_runtime(app_context, test_app)
    runtime.accept_shutdown("service")
    response = await unauth_client.get(
        "/api/runtime/readiness",
        headers={"X-BSM-Readiness-Token": runtime._readiness_token},
    )
    assert response.status_code == 200
    assert response.json()["runtime"]["phase"] == "stopping"
    assert response.json()["health"]["ready"] is False
    assert response.json()["health"]["checks"]["lifecycle"]["healthy"] is False


def test_control_record_publishes_distinct_private_rotating_capabilities(tmp_path):
    runtime = WebRuntime()
    files = ControlFiles(tmp_path, runtime)
    files.acquire()
    try:
        files.publish("0.0.0.0", 11325)
        paths = WebProcessPaths(
            config_dir=str(tmp_path), data_dir=str(tmp_path), db_url="sqlite:///test"
        )
        record = read_control(paths)
        assert record.readiness_token.get_secret_value() == runtime._readiness_token
        assert (
            record.token.get_secret_value() != record.readiness_token.get_secret_value()
        )
        assert runtime._readiness_token not in repr(record)
        if os.name != "nt":
            assert paths.control_file.stat().st_mode & 0o777 == 0o600
        other = WebRuntime()
        assert not other.authenticate_readiness(runtime._readiness_token)
        assert not runtime.authenticate_readiness("é")
    finally:
        files.close()
    assert not (tmp_path / "web_server.control.json").exists()
