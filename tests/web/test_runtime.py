"""Real ASGI authorization, local control and runtime transitions."""

import os

import pytest

from bedrock_server_manager.error import OperationConflictError
from bedrock_server_manager.services.lifecycle import LifecyclePhase
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


async def test_shutdown_requires_admin_and_is_idempotent(
    app_context, test_app, unauth_client, auth_client, admin_auth_client
):
    runtime, server = attach_runtime(app_context, test_app)
    assert (
        await unauth_client.post("/api/runtime/shutdown", json={})
    ).status_code == 401
    assert (await auth_client.post("/api/runtime/shutdown", json={})).status_code == 403
    assert not server.should_exit
    response = await admin_auth_client.post("/api/runtime/shutdown", json={})
    assert response.status_code == 202
    assert response.json()["shutdown_reason"] == "administrator"
    assert response.json()["phase"] == "stopping"
    assert server.should_exit
    second = await admin_auth_client.post("/api/runtime/shutdown", json={})
    assert second.json() == response.json()
    assert (await admin_auth_client.get("/api/runtime")).json()["shutdown_requested"]
    assert runtime.snapshot().phase == LifecyclePhase.STOPPING
    assert (
        await admin_auth_client.post("/api/server/install", json={})
    ).status_code == 503


async def test_unmanaged_asgi_host_reports_control_unavailable(admin_auth_client):
    assert (
        await admin_auth_client.post("/api/runtime/shutdown", json={})
    ).status_code == 503


async def test_local_capability_is_shutdown_only_and_invalid_tokens_fail(
    app_context, test_app, unauth_client, admin_auth_client
):
    runtime, server = attach_runtime(app_context, test_app)
    assert (
        await unauth_client.post(
            "/api/runtime/shutdown",
            json={},
            headers={"X-BSM-Shutdown-Token": "invalid"},
        )
    ).status_code == 401
    headers = {"X-BSM-Shutdown-Token": runtime._token}
    assert (await unauth_client.get("/api/runtime", headers=headers)).status_code == 401
    assert (
        await unauth_client.post(
            "/api/runtime/shutdown", json={"force": True}, headers=headers
        )
    ).status_code == 422
    response = await unauth_client.post(
        "/api/runtime/shutdown", json={}, headers=headers
    )
    assert response.status_code == 202
    assert response.json()["shutdown_reason"] == "local_cli"
    assert server.should_exit
    assert runtime._token not in response.text


def test_control_lock_and_owner_cleanup(tmp_path):
    runtime = WebRuntime()
    files = ControlFiles(tmp_path, runtime)
    files.acquire()
    files.publish("0.0.0.0", 11325)
    paths = WebProcessPaths(
        config_dir=str(tmp_path), data_dir=str(tmp_path), db_url="sqlite:///test"
    )
    record = read_control(paths)
    assert record.instance_id == runtime.instance_id
    assert record.host == "127.0.0.1"
    assert record.token.get_secret_value() == runtime._token
    if os.name != "nt":
        assert paths.control_file.stat().st_mode & 0o777 == 0o600
    other = ControlFiles(tmp_path, WebRuntime())
    with pytest.raises(OperationConflictError):
        other.acquire()
    other.close()
    assert paths.control_file.exists()
    files.close()
    assert not paths.control_file.exists()
    assert not (tmp_path / "web_server.pid").exists()
    other.acquire()
    other.close()


def test_service_stop_before_attach_is_retained():
    runtime = WebRuntime()
    runtime.request_shutdown("service")
    exits = []
    runtime.attach(lambda: exits.append(True))
    runtime.ready()
    assert exits == [True]
    assert runtime.snapshot().phase == LifecyclePhase.STOPPING
    runtime.finish()
    assert runtime.snapshot().phase == LifecyclePhase.STOPPED
    with pytest.raises(OperationConflictError):
        runtime.attach(lambda: None)


def test_systemd_web_unit_uses_clean_exit_policy(app_context, systemd):
    from bedrock_server_manager.core.service import create_web_service_file

    create_web_service_file(app_context.data_dir)
    content = systemd.path().read_text()
    assert "Restart=on-failure" in content
    assert "TimeoutStopSec=180s" in content
    assert "ExecStop=" not in content


def test_stale_control_is_replaced_only_after_lock_acquired(tmp_path):
    (tmp_path / "web_server.control.json").write_text("corrupt")
    files = ControlFiles(tmp_path, WebRuntime())
    files.acquire()
    files.publish("::", 8080)
    paths = WebProcessPaths(
        config_dir=str(tmp_path), data_dir=str(tmp_path), db_url="sqlite:///test"
    )
    assert read_control(paths).url == "http://[::1]:8080/api/runtime/shutdown"
    files.close()


def test_runtime_token_comparison_rejects_non_ascii():
    assert not WebRuntime().authenticate_local("é")


async def test_force_stop_requires_verified_legacy_identity(tmp_path):
    from bedrock_server_manager.error import ServerStopError
    from bedrock_server_manager.web.process import stop_local

    paths = WebProcessPaths(
        config_dir=str(tmp_path), data_dir=str(tmp_path), db_url="sqlite:///test"
    )
    pid = tmp_path / "web_server.pid"
    pid.write_text(str(os.getpid()))
    with pytest.raises(ServerStopError, match="No graceful"):
        await stop_local(paths)
    # The running pytest process must never be terminated merely because a PID file names it.
    from bedrock_server_manager.error import ServerProcessError

    with pytest.raises(ServerProcessError):
        await stop_local(paths, force=True)
    assert pid.exists()


async def test_shutdown_drains_inflight_request_before_lifespan_cleanup(app_context):
    import asyncio
    import socket

    from httpx2 import AsyncClient, TransportError

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    runtime = WebRuntime()
    server = create_server(
        app_context, WebRunOptions(host="127.0.0.1", port=port), runtime
    )
    entered, release = asyncio.Event(), asyncio.Event()

    @server.config.app.get("/api/slow-runtime-test", include_in_schema=False)
    async def slow():
        entered.set()
        await release.wait()
        # Lifespan cleanup must not dispose dependencies while this request runs.
        assert app_context.db.engine is not None
        return {"finished": True}

    serving = asyncio.create_task(server.serve())
    pending = None
    try:
        async with AsyncClient(timeout=10, trust_env=False) as client:
            async with asyncio.timeout(10):
                while True:
                    try:
                        response = await client.get(f"http://127.0.0.1:{port}/api/info")
                        if response.status_code == 200:
                            break
                    except TransportError:
                        pass
                    await asyncio.sleep(0.01)
            pending = asyncio.create_task(
                client.get(f"http://127.0.0.1:{port}/api/slow-runtime-test")
            )
            await asyncio.wait_for(entered.wait(), 5)
            response = await client.post(
                f"http://127.0.0.1:{port}/api/runtime/shutdown",
                json={},
                headers={"X-BSM-Shutdown-Token": runtime._token},
            )
            assert response.status_code == 202
            assert not serving.done()
            assert app_context.lifecycle_phase == LifecyclePhase.READY
            release.set()
            assert (await pending).json() == {"finished": True}
            await asyncio.wait_for(serving, 10)
            assert app_context.lifecycle_phase == LifecyclePhase.STOPPED
            assert runtime.snapshot().phase == LifecyclePhase.STOPPED
            assert app_context.db.engine is None
    finally:
        release.set()
        server.should_exit = True
        if pending is not None:
            await asyncio.gather(pending, return_exceptions=True)
        await asyncio.wait_for(serving, 10)
