"""Check complete submissions to background APIs, rather than task IDs alone."""

import inspect
from unittest.mock import patch

import pytest

from bedrock_server_manager.api import addon as addon_api
from bedrock_server_manager.api import install as install_api
from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.plugins.api_contract import get_contract
from bedrock_server_manager.web.routers import addon, install, server_actions, world
from bedrock_server_manager.web.schemas import (
    AddonActionPayload,
    AddonReorderPayload,
    AddonSubpackPayload,
    FileNamePayload,
    InstallServerPayload,
)


@pytest.mark.parametrize(
    "route, target, payload, expected",
    [
        (
            addon.post_enable_addon,
            addon_api.enable_addon,
            AddonActionPayload(pack_uuid="pack", pack_type="behavior"),
            {"pack_uuid": "pack", "pack_type": "behavior"},
        ),
        (
            addon.post_disable_addon,
            addon_api.disable_addon,
            AddonActionPayload(pack_uuid="pack", pack_type="resource"),
            {"pack_uuid": "pack", "pack_type": "resource"},
        ),
        (
            addon.post_update_subpack,
            addon_api.update_subpack,
            AddonSubpackPayload(
                pack_uuid="pack", pack_type="behavior", subpack_name="variant"
            ),
            {"pack_uuid": "pack", "pack_type": "behavior", "subpack_name": "variant"},
        ),
        (
            addon.delete_uninstall_addon,
            addon_api.uninstall_addon,
            AddonActionPayload(pack_uuid="pack", pack_type="resource"),
            {"pack_uuid": "pack", "pack_type": "resource"},
        ),
        (
            addon.post_reorder_addons,
            addon_api.reorder_addons,
            AddonReorderPayload(pack_type="behavior", uuids=["first", "second"]),
            {"pack_type": "behavior", "uuids": ["first", "second"]},
        ),
        (
            addon.post_install_addon,
            addon_api.import_addon,
            FileNamePayload(filename="pack.mcaddon"),
            {"addon_file_path": "addons/pack.mcaddon"},
        ),
        (
            world.post_world_install,
            world_api.import_world,
            FileNamePayload(filename="world.mcworld"),
            {"selected_file_path": "worlds/world.mcworld"},
        ),
        (world.post_world_export, world_api.export_world, None, {}),
        (world.delete_world_reset, world_api.reset_world, None, {}),
        (server_actions.post_update_server, install_api.update_server, None, {}),
        (server_actions.delete_server, server_api.delete_server_data, None, {}),
    ],
)
async def test_route_task_submission_matches_api_contract(
    app_context,
    real_bedrock_server,
    test_user,
    tmp_path,
    route,
    target,
    payload,
    expected,
):
    content = tmp_path / "content"
    for relative in ("addons/pack.mcaddon", "worlds/world.mcworld"):
        file = content / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    await app_context.settings.set("paths.content", str(content))

    async def validate_submission(function, *, username, app_context: object, request):
        assert function is target
        assert username == test_user.username
        inspect.signature(function).bind(request=request, app_context=app_context)
        contract = get_contract(function)
        assert contract is not None
        assert type(request) is contract[0]
        validated = contract[0].model_validate(request)
        assert getattr(validated, "server_name") == real_bedrock_server.server_name
        for field, value in expected.items():
            if field in {"addon_file_path", "selected_file_path"}:
                value = str(content / value)
            assert getattr(validated, field) == value
        return "checked-task"

    kwargs = {
        "server_name": real_bedrock_server.server_name,
        "current_user": test_user,
        "app_context": app_context,
    }
    if payload is not None:
        kwargs["payload"] = payload
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        side_effect=validate_submission,
    ) as submit:
        response = await route(**kwargs)
    assert response.task_id == "checked-task"
    submit.assert_awaited_once()
    assert submit.await_args.kwargs["app_context"] is app_context


@pytest.mark.parametrize("version", ["LATEST", "CUSTOM"])
async def test_install_task_submission_matches_api_contract(
    app_context, test_user, tmp_path, version
):
    downloads = tmp_path / "downloads"
    await app_context.settings.set("paths.downloads", str(downloads))
    payload = InstallServerPayload(
        server_name="new_server",
        server_version=version,
        server_zip_path="custom.zip" if version == "CUSTOM" else None,
    )
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="install-task",
    ) as submit:
        response = await install.post_install_server(
            payload=payload, current_user=test_user, app_context=app_context
        )
    assert response.task_id == "install-task"
    assert submit.await_args.args == (install_api.install_new_server,)
    kwargs = submit.await_args.kwargs
    assert set(kwargs) == {"username", "app_context", "request"}
    assert kwargs["username"] == test_user.username
    assert kwargs["app_context"] is app_context
    inspect.signature(install_api.install_new_server).bind(
        request=kwargs["request"], app_context=app_context
    )
    contract = get_contract(install_api.install_new_server)
    assert type(kwargs["request"]) is contract[0]
    request = contract[0].model_validate(kwargs["request"])
    assert request.server_name == "new_server"
    assert request.target_version == version
    assert request.server_zip_path == (
        str(downloads / "custom/custom.zip") if version == "CUSTOM" else None
    )


async def test_plugin_task_request_survives_runtime_bridge(
    app_context, real_bedrock_server
):
    from bedrock_server_manager.api.models import StartServerRequest
    from bedrock_server_manager.plugins.api_bridge import create_app_api

    api = create_app_api("autostart", app_context)
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="autostart-task",
    ) as submit:
        task_id = await api.runtime.run_task(
            api.server.start,
            request={"server_name": real_bedrock_server.server_name},
            username="System (Autostart)",
        )
    assert task_id == "autostart-task"
    submit.assert_awaited_once()
    call = submit.await_args
    assert call.args[1:] == ("System (Autostart)",)
    assert set(call.kwargs) == {"request", "_plugin_owner"}
    assert call.kwargs["_plugin_owner"] == "autostart"
    target = call.args[0]
    inspect.signature(target).bind(request=call.kwargs["request"])
    request = StartServerRequest.model_validate(call.kwargs["request"])
    # The bridge supplies runtime context itself; request data stays unchanged.
    with patch.object(real_bedrock_server, "is_running", return_value=True):
        result = await target(request=request)
    assert result.server_name == real_bedrock_server.server_name
    assert result.outcome == "already_running"
