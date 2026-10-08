import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.addon import (
    disable_addon,
    enable_addon,
    import_addon,
    list_installed_addons,
    reorder_addons,
    uninstall_addon,
    update_subpack,
)
from bedrock_server_manager.api.models import (
    DisableAddonRequest,
    EnableAddonRequest,
    ImportAddonRequest,
    ListInstalledAddonsRequest,
    ReorderAddonsRequest,
    UninstallAddonRequest,
    UpdateSubpackRequest,
)
from bedrock_server_manager.error import BSMError


async def test_addon_lifecycle_persists_world_activation(
    app_context, populated_server, valid_behavior_pack_zip
):
    name = populated_server.server_name
    await import_addon(
        ImportAddonRequest(
            server_name=name,
            addon_file_path=str(valid_behavior_pack_zip),
            stop_start_server=False,
        ),
        app_context=app_context,
    )

    async def packs():
        return (
            await list_installed_addons(
                ListInstalledAddonsRequest(server_name=name), app_context=app_context
            )
        ).addons.behavior_packs

    addon = next(pack for pack in await packs() if pack.name == "Valid BP Zip")
    assert addon.status == "ACTIVE"
    world = (
        Path(populated_server.server_dir)
        / "worlds"
        / await populated_server.get_world_name()
    )
    activation = world / "world_behavior_packs.json"
    assert addon.uuid in {
        entry["pack_id"] for entry in json.loads(activation.read_text())
    }
    fields = dict(server_name=name, pack_uuid=addon.uuid, pack_type="behavior")
    await disable_addon(DisableAddonRequest(**fields), app_context=app_context)
    assert (
        next(pack for pack in await packs() if pack.uuid == addon.uuid).status
        == "INACTIVE"
    )
    await enable_addon(EnableAddonRequest(**fields), app_context=app_context)
    assert (
        next(pack for pack in await packs() if pack.uuid == addon.uuid).status
        == "ACTIVE"
    )
    active = [pack.uuid for pack in await packs() if pack.status == "ACTIVE"]
    await reorder_addons(
        ReorderAddonsRequest(
            server_name=name, pack_type="behavior", uuids=list(reversed(active))
        ),
        app_context=app_context,
    )
    assert [entry["pack_id"] for entry in json.loads(activation.read_text())] == list(
        reversed(active)
    )
    await uninstall_addon(UninstallAddonRequest(**fields), app_context=app_context)
    assert addon.uuid not in {pack.uuid for pack in await packs()}


async def test_invalid_archive_preserves_installed_addons(
    app_context, populated_server, tmp_path
):
    before = await list_installed_addons(
        ListInstalledAddonsRequest(server_name=populated_server.server_name),
        app_context=app_context,
    )
    archive = tmp_path / "broken.mcpack"
    archive.write_bytes(b"not an archive")
    with pytest.raises(BSMError):
        await import_addon(
            ImportAddonRequest(
                server_name=populated_server.server_name,
                addon_file_path=str(archive),
                stop_start_server=False,
            ),
            app_context=app_context,
        )
    after = await list_installed_addons(
        ListInstalledAddonsRequest(server_name=populated_server.server_name),
        app_context=app_context,
    )
    assert after == before
    assert not populated_server.operation_lock.locked()


async def test_unknown_pack_preserves_activation(app_context, populated_server):
    before = await list_installed_addons(
        ListInstalledAddonsRequest(server_name=populated_server.server_name),
        app_context=app_context,
    )
    with pytest.raises(BSMError):
        await update_subpack(
            UpdateSubpackRequest(
                server_name=populated_server.server_name,
                pack_uuid="missing-pack",
                pack_type="resource",
                subpack_name="missing",
            ),
            app_context=app_context,
        )
    assert (
        await list_installed_addons(
            ListInstalledAddonsRequest(server_name=populated_server.server_name),
            app_context=app_context,
        )
        == before
    )


@pytest.mark.parametrize("pack_type", ["invalid", "", "behavior_packs"])
def test_addon_requests_reject_invalid_pack_type(pack_type):
    with pytest.raises(ValidationError):
        EnableAddonRequest(
            server_name="test_server", pack_uuid="uuid", pack_type=pack_type
        )
