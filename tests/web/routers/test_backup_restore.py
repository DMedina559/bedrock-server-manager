from pathlib import Path

import pytest


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


"""HTTP archive operations execute real background tasks and preserve credentials."""


async def task_result(client, context, response, wait_for_task):
    assert response.status_code == 202, response.text
    identifier = response.json()["task_id"]
    await wait_for_task(context, identifier)
    snapshot = await client.get(f"/api/tasks/status/{identifier}")
    body = snapshot.json()
    assert body["status"] == "completed", body
    return body["result"]


async def test_http_create_inspect_plan_restore(
    admin_auth_client, app_context, populated_server, wait_for_task
):
    client = admin_auth_client
    base = f"/api/server/{populated_server.server_name}/backups"
    created = await task_result(
        client, app_context, await client.post(base, json={}), wait_for_task
    )
    identifier = created["backup"]["backup_id"]
    assert identifier.endswith(".bsmbackup")
    inspected = await task_result(
        client,
        app_context,
        await client.post(f"{base}/{identifier}/inspect", json={}),
        wait_for_task,
    )
    assert inspected["backup"]["manifest"]["components"]["bsm_settings"] == "included"
    properties = Path(populated_server.paths.server_properties_path)
    original = properties.read_bytes()
    properties.write_text(properties.read_text() + "\nserver-name=changed\n")
    planned = await task_result(
        client,
        app_context,
        await client.post(
            f"{base}/{identifier}/plan", json={"components": ["server.properties"]}
        ),
        wait_for_task,
    )
    restored = await task_result(
        client,
        app_context,
        await client.post(
            f"{base}/{identifier}/restore",
            json={
                "components": ["server.properties"],
                "token": planned["plan"]["token"],
            },
        ),
        wait_for_task,
    )
    assert restored["result"]["committed"]
    assert properties.read_bytes() == original
    downloaded = await client.get(f"{base}/{identifier}/download")
    assert downloaded.status_code == 200
    uploaded = await client.post(
        f"{base}/import",
        files={
            "file": ("backup.bsmbackup", downloaded.content, "application/octet-stream")
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    assert len(uploaded.json()["backups"]) == 3
    assert restored["result"]["safety_backup_id"]


async def test_recovery_key_is_not_in_tasks_or_diagnostics(
    admin_auth_client, app_context, populated_server, wait_for_task
):
    key = populated_server.backups.credentials.rotate()
    base = f"/api/server/{populated_server.server_name}/backups"
    created = await task_result(
        admin_auth_client,
        app_context,
        await admin_auth_client.post(base, json={"encrypted": True}),
        wait_for_task,
    )
    identifier = created["backup"]["backup_id"]
    response = await admin_auth_client.post(
        f"{base}/{identifier}/inspect",
        json={"recovery_key": key.secret.get_secret_value()},
    )
    result = await task_result(admin_auth_client, app_context, response, wait_for_task)
    assert result["backup"]["encrypted"]
    tasks = await admin_auth_client.get("/api/tasks/list")
    assert key.secret.get_secret_value() not in tasks.text
    metadata = await admin_auth_client.get("/api/backups/keys")
    assert key.secret.get_secret_value() not in metadata.text
    kit = await admin_auth_client.get(f"/api/backups/keys/{key.key_id}/emergency-kit")
    assert key.secret.get_secret_value() in kit.text
    assert kit.headers["cache-control"] == "no-store"


async def test_snapshot_authorization(auth_client, real_bedrock_server):
    response = await auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/backups", json={}
    )
    assert response.status_code == 403
    assert (await auth_client.get("/api/backups/keys")).status_code == 403


async def test_http_recovery_inspection_and_retry(
    admin_auth_client, app_context, populated_server, wait_for_task, tmp_path
):
    from bedrock_server_manager.backups.recovery import RestoreJournal

    server = populated_server
    original = Path(server.paths.allowlist_json_path).read_bytes()
    journal = RestoreJournal(server)
    journal.begin(["allowlist.json"], False)
    replacement = tmp_path / "replacement"
    replacement.write_text('[{"name":"changed"}]')
    journal.replace(0, replacement)
    endpoint = f"/api/server/{server.server_name}/backups/recovery"
    status = await admin_auth_client.get(endpoint)
    assert status.json()["recovery"]["active"]
    result = await task_result(
        admin_auth_client,
        app_context,
        await admin_auth_client.post(endpoint),
        wait_for_task,
    )
    assert not result["recovery"]["active"]
    assert Path(server.paths.allowlist_json_path).read_bytes() == original


async def test_backup_health_management_and_native_upload_limit(
    admin_auth_client, app_context, populated_server, wait_for_task
):
    client = admin_auth_client
    base = f"/api/server/{populated_server.server_name}/backups"
    created = await task_result(
        client, app_context, await client.post(base, json={}), wait_for_task
    )
    identifier = created["backup"]["backup_id"]
    for action in ("verify", "pin", "unpin"):
        await task_result(
            client,
            app_context,
            await client.post(f"{base}/{identifier}/manage", json={"action": action}),
            wait_for_task,
        )
    health = await client.get(f"{base}/health")
    assert health.status_code == 200 and health.json()["health"]["last_verified_at"]
    await app_context.settings.set("backups.max_archive_bytes", 1)
    too_large = await client.post(
        f"{base}/import", files={"file": ("huge.bsmbackup", b"x" * 70000)}
    )
    assert too_large.status_code == 413


async def test_recovery_report_download_is_redacted_and_not_cached(
    admin_auth_client, populated_server
):
    snapshot = await populated_server.backups.create_snapshot()
    response = await admin_auth_client.get(
        f"/api/server/{populated_server.server_name}/backups/report"
    )
    assert response.status_code == 200
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="bsm-recovery-report.json"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert snapshot.filename not in response.text
    assert populated_server.paths.server_dir not in response.text
    assert response.json()["report"]["report_version"] == 1


async def test_recovery_report_requires_moderation(auth_client, real_bedrock_server):
    response = await auth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/backups/report"
    )
    assert response.status_code == 403


async def test_slow_drill_keeps_reads_responsive_and_mutations_serialized(
    admin_auth_client, app_context, populated_server, wait_for_task, monkeypatch
):
    import asyncio
    import threading

    from bedrock_server_manager.backups import server as implementation

    server = populated_server
    snapshot = await server.backups.create_snapshot(mode="world")
    entered, release = threading.Event(), threading.Event()
    original = implementation.verify_staging

    def slow(*args, cancellation_event=None, stage_callback=None, **kwargs):
        entered.set()
        while not release.wait(0.01):
            from bedrock_server_manager.utils.threads import check_cancellation

            check_cancellation(cancellation_event)
        return original(
            *args,
            cancellation_event=cancellation_event,
            stage_callback=stage_callback,
            **kwargs,
        )

    monkeypatch.setattr(implementation, "verify_staging", slow)
    client = admin_auth_client
    base = f"/api/server/{server.server_name}/backups"
    response = await client.post(
        f"{base}/{snapshot.backup_id}/manage", json={"action": "drill"}
    )
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    waiting = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 5), 6)

        async def mutate():
            async with server.operation_lock:
                return True

        waiting = asyncio.create_task(mutate())
        for url in (
            "/api/account",
            "/api/servers",
            base,
            f"{base}/health",
            f"/api/tasks/status/{task_id}",
        ):
            observed = await asyncio.wait_for(client.get(url), 2)
            assert observed.status_code == 200, observed.text
        assert not waiting.done(), "Server mutation escaped drill serialization"
    finally:
        release.set()
        await wait_for_task(app_context, task_id)
        if waiting is not None:
            await waiting
    result = await client.get(f"/api/tasks/status/{task_id}")
    assert result.json()["status"] == "completed"
