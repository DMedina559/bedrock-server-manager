from bedrock_server_manager.plugins.api_bridge import create_app_api


async def test_plugin_task_bridge_runs_actual_server_api(
    app_context, real_bedrock_server, wait_for_task
):
    api = create_app_api("autostart", app_context)
    task_id = await api.runtime.run_task(
        api.server.start,
        request={"server_name": real_bedrock_server.server_name},
        username="System (Autostart)",
    )
    snapshot = await wait_for_task(app_context, task_id)
    assert snapshot.result["server_name"] == real_bedrock_server.server_name
    assert snapshot.result["outcome"] == "started"
    assert await real_bedrock_server.is_running()
    assert app_context.task_manager._plugin_owners[task_id] == "autostart"
    assert await app_context.task_manager.get_task(task_id, username="other") is None
