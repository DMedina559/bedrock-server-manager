import asyncio

import pytest

from bedrock_server_manager.api.models import GetGlobalSettingRequest
from bedrock_server_manager.api.settings import get_global_setting


async def test_task_status_tracks_real_api_work(
    auth_client, app_context, test_user, wait_for_task
):
    task_id = await app_context.task_manager.run_task(
        get_global_setting,
        test_user.username,
        GetGlobalSettingRequest(key="web.port"),
        app_context=app_context,
    )
    await wait_for_task(app_context, task_id)
    response = await auth_client.get(f"/api/tasks/status/{task_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["value"] == app_context.settings.get("web.port")
    tasks = (await auth_client.get("/api/tasks/list")).json()
    assert [task["id"] for task in tasks] == [task_id]


async def test_task_visibility_is_scoped_to_user(
    auth_client, admin_auth_client, app_context, test_admin_user, wait_for_task
):
    task_id = await app_context.task_manager.run_task(
        get_global_setting,
        test_admin_user.username,
        GetGlobalSettingRequest(key="web.port"),
        app_context=app_context,
    )
    await wait_for_task(app_context, task_id)
    assert (await auth_client.get(f"/api/tasks/status/{task_id}")).status_code == 404
    assert (await auth_client.get("/api/tasks/list")).json() == []
    assert (
        await admin_auth_client.get(f"/api/tasks/status/{task_id}")
    ).status_code == 200


async def test_task_reports_running_then_completed(
    auth_client, app_context, test_user, wait_for_task
):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def work():
        entered.set()
        await release.wait()
        return {"finished": True}

    task_id = await app_context.task_manager.run_task(work, test_user.username)
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert (await auth_client.get(f"/api/tasks/status/{task_id}")).json()[
            "status"
        ] == "running"
    finally:
        release.set()
    await wait_for_task(app_context, task_id)
    assert (await auth_client.get(f"/api/tasks/status/{task_id}")).json()["result"] == {
        "finished": True
    }


@pytest.mark.parametrize("path", ["/api/tasks/status/missing", "/api/tasks/list"])
async def test_task_endpoints_require_authentication(unauth_client, path):
    assert (await unauth_client.get(path)).status_code == 401


async def test_unknown_task_is_not_found(auth_client):
    assert (await auth_client.get("/api/tasks/status/missing")).status_code == 404
