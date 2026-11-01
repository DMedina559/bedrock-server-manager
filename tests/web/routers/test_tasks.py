import asyncio

from bedrock_server_manager.api.models import GetGlobalSettingRequest
from bedrock_server_manager.api.settings import get_global_setting


async def test_task_lifecycle_visibility_and_auth(
    unauth_client,
    auth_client,
    admin_auth_client,
    app_context,
    test_user,
    test_admin_user,
    wait_for_task,
):
    # Unauthenticated and missing task checks
    for path in ("/api/tasks/status/missing", "/api/tasks/list"):
        assert (await unauth_client.get(path)).status_code == 401
    assert (await auth_client.get("/api/tasks/status/missing")).status_code == 404

    # Real API work tracked and scoped to user
    user_task_id = await app_context.task_manager.run_task(
        get_global_setting,
        test_user.username,
        GetGlobalSettingRequest(key="web.port"),
        app_context=app_context,
    )
    await wait_for_task(app_context, user_task_id)
    response = await auth_client.get(f"/api/tasks/status/{user_task_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["value"] == app_context.settings.get("web.port")
    tasks = (await auth_client.get("/api/tasks/list")).json()
    assert [task["id"] for task in tasks] == [user_task_id]

    admin_task_id = await app_context.task_manager.run_task(
        get_global_setting,
        test_admin_user.username,
        GetGlobalSettingRequest(key="web.port"),
        app_context=app_context,
    )
    await wait_for_task(app_context, admin_task_id)
    assert (
        await auth_client.get(f"/api/tasks/status/{admin_task_id}")
    ).status_code == 404
    assert (
        await admin_auth_client.get(f"/api/tasks/status/{admin_task_id}")
    ).status_code == 200

    # Running then completed transition
    entered = asyncio.Event()
    release = asyncio.Event()

    async def work():
        entered.set()
        await release.wait()
        return {"finished": True}

    run_task_id = await app_context.task_manager.run_task(work, test_user.username)
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert (await auth_client.get(f"/api/tasks/status/{run_task_id}")).json()[
            "status"
        ] == "running"
    finally:
        release.set()
    await wait_for_task(app_context, run_task_id)
    assert (await auth_client.get(f"/api/tasks/status/{run_task_id}")).json()[
        "result"
    ] == {"finished": True}
