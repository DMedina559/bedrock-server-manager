import json
import os
from unittest.mock import patch

import pytest
from bsm_test_utils import create_behavior_pack, create_resource_pack
from pydantic import ValidationError

from bedrock_server_manager.api.models.addon import ListInstalledAddonsResponse
from bedrock_server_manager.core.data import SubpackRecord


async def test_list_installed_addons(real_bedrock_server):
    """Test listing installed addons in physical folders."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        os.makedirs(os.path.join(world_dir, "behavior_packs"), exist_ok=True)
        os.makedirs(os.path.join(world_dir, "resource_packs"), exist_ok=True)

        bp_path = create_behavior_pack(
            os.path.join(world_dir, "behavior_packs"), name="bp1", as_zip=False
        )
        rp_path = create_resource_pack(
            os.path.join(world_dir, "resource_packs"), name="rp1", as_zip=False
        )

        with open(os.path.join(bp_path, "manifest.json")) as f:
            bp_uuid = json.load(f)["header"]["uuid"]
        with open(os.path.join(rp_path, "manifest.json")) as f:
            rp_uuid = json.load(f)["header"]["uuid"]

        addons = await server.addons.list_installed_addons()
        assert len(addons["behavior_packs"]) == 1
        assert len(addons["resource_packs"]) == 1
        assert addons["behavior_packs"][0]["uuid"] == bp_uuid
        assert addons["resource_packs"][0]["uuid"] == rp_uuid


async def test_enable_disable_addon(real_bedrock_server):
    """Test enabling and disabling an addon."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        os.makedirs(os.path.join(world_dir, "behavior_packs"), exist_ok=True)

        bp_path = create_behavior_pack(
            os.path.join(world_dir, "behavior_packs"), name="bp1", as_zip=False
        )
        with open(os.path.join(bp_path, "manifest.json")) as f:
            bp_uuid = json.load(f)["header"]["uuid"]

        # Test Enable
        await server.addons.enable_addon(bp_uuid, "behavior")

        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        bp_json_path = os.path.join(world_dir, "world_behavior_packs.json")
        assert os.path.exists(bp_json_path)

        with open(bp_json_path, "r") as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["pack_id"] == bp_uuid

        # Check list shows it as enabled (ACTIVE)
        addons = await server.addons.list_installed_addons()
        bp = addons["behavior_packs"][0]
        assert bp["status"] == "ACTIVE"

        # Test Disable
        await server.addons.disable_addon(bp_uuid, "behavior")

        with open(bp_json_path, "r") as f:
            data = json.load(f)
            assert len(data) == 0

        # Check list shows it as disabled (INACTIVE)
        addons = await server.addons.list_installed_addons()
        bp = addons["behavior_packs"][0]
        assert bp["status"] == "INACTIVE"


async def test_process_mcpack_archive(real_bedrock_server, tmp_path):
    """Test processing an mcpack file."""
    server = real_bedrock_server

    import shutil

    # create_behavior_pack doesn't natively accept 'extension' or 'uuid' directly.
    # We create a zip then rename it to .mcpack
    zip_path = create_behavior_pack(str(tmp_path), name="test_pack", as_zip=True)
    mcpack_path = tmp_path / "test_pack.mcpack"
    shutil.move(str(zip_path), str(mcpack_path))

    with patch.object(server, "get_world_name", return_value="test_world"):
        await server.addons.process_addon_file(str(mcpack_path))

        # Should be physically installed
        addons = await server.addons.list_installed_addons()
        assert len(addons["behavior_packs"]) == 1

        # We don't know the exact uuid since it's auto-generated, but it should be enabled
        assert (
            addons["behavior_packs"][0]["status"] == "ACTIVE"
        )  # Auto-enabled on install


async def test_remove_addon(real_bedrock_server):
    """Test removing an addon deletes physical files and removes from active JSON."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        os.makedirs(os.path.join(world_dir, "behavior_packs"), exist_ok=True)

        bp_path = create_behavior_pack(
            os.path.join(world_dir, "behavior_packs"), name="bp_rem", as_zip=False
        )
        with open(os.path.join(bp_path, "manifest.json")) as f:
            bp_uuid = json.load(f)["header"]["uuid"]

        await server.addons.enable_addon(bp_uuid, "behavior")

        await server.addons.remove_addon(bp_uuid, "behavior")

        addons = await server.addons.list_installed_addons()
        assert len(addons["behavior_packs"]) == 0

        # Verify JSON is empty
        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        bp_json_path = os.path.join(world_dir, "world_behavior_packs.json")
        with open(bp_json_path, "r") as f:
            data = json.load(f)
            assert len(data) == 0


async def test_reorder_addons(real_bedrock_server):
    """Test reordering enabled addons."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        os.makedirs(os.path.join(world_dir, "behavior_packs"), exist_ok=True)

        bp1_path = create_behavior_pack(
            os.path.join(world_dir, "behavior_packs"), name="bp1", as_zip=False
        )
        bp2_path = create_behavior_pack(
            os.path.join(world_dir, "behavior_packs"), name="bp2", as_zip=False
        )

        with open(os.path.join(bp1_path, "manifest.json")) as f:
            uuid_1 = json.load(f)["header"]["uuid"]
        with open(os.path.join(bp2_path, "manifest.json")) as f:
            uuid_2 = json.load(f)["header"]["uuid"]

        await server.addons.enable_addon(uuid_1, "behavior")
        await server.addons.enable_addon(uuid_2, "behavior")

        # Reorder sending uuid-2 first
        await server.addons.reorder_addons([uuid_2, uuid_1], "behavior")

        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        bp_json_path = os.path.join(world_dir, "world_behavior_packs.json")
        with open(bp_json_path, "r") as f:
            data = json.load(f)
            assert data[0]["pack_id"] == uuid_2
            assert data[1]["pack_id"] == uuid_1


async def test_process_invalid_mcpack_archive(real_bedrock_server, tmp_path):
    """Test processing an uploaded .mcpack archive that is corrupt (invalid json)."""
    server = real_bedrock_server

    import shutil

    # Create an invalid pack
    zip_path = create_behavior_pack(
        str(tmp_path), name="test_invalid_pack", as_zip=True, invalid_json=True
    )
    mcpack_path = tmp_path / "test_invalid_pack.mcpack"
    shutil.move(str(zip_path), str(mcpack_path))

    with patch.object(server, "get_world_name", return_value="test_world"):
        # Need to ensure the world dir physically exists for list_installed_addons to not fail on missing dir
        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        os.makedirs(world_dir, exist_ok=True)

        # Processing might log an error or raise depending on the mixin implementation.
        # Since invalid_json is true, it won't be able to extract a valid UUID from manifest.
        # Ensure it handles the corrupted pack gracefully or raises an expected error.
        try:
            await server.addons.process_addon_file(str(mcpack_path))
        except Exception:
            pass  # Depending on exactly how process_addon_file reacts to json.decoder.JSONDecodeError

        # In any case, it should not be listed as a correctly installed addon with a valid UUID
        addons = await server.addons.list_installed_addons()
        # Even if it extracted, it couldn't parse the UUID properly.
        # Most likely behavior packs list will be empty or not contain a valid entry.
        assert len(addons.get("behavior_packs", [])) == 0


@pytest.mark.parametrize("extra_pack", [False, True])
async def test_subpack_manifest_extensions_do_not_break_listing(
    real_bedrock_server, extra_pack
):
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        packs_dir = os.path.join(
            server.paths.server_dir, "worlds", "test_world", "resource_packs"
        )
        os.makedirs(packs_dir, exist_ok=True)
        pack_path = create_resource_pack(packs_dir, name="subpacks", as_zip=False)
        manifest_path = os.path.join(pack_path, "manifest.json")
        with open(manifest_path) as stream:
            manifest = json.load(stream)
        manifest["subpacks"] = [
            {
                "folder_name": f"variant_{index}",
                "name": f"Variant {index}",
                "memory_performance_tier": index,
                "extension": {"future": True},
            }
            for index in range(5)
        ]
        original = json.dumps(manifest)
        with open(manifest_path, "w") as stream:
            stream.write(original)
        if extra_pack:
            create_resource_pack(packs_dir, name="ordinary", as_zip=False)

        addons = await server.addons.list_installed_addons()
        response = ListInstalledAddonsResponse.model_validate(
            {"status": "success", "addons": addons}
        )
        pack = next(p for p in response.addons.resource_packs if p.subpacks)
        assert [p.memory_tier for p in pack.subpacks] == list(range(5))
        assert len(response.addons.resource_packs) == 1 + extra_pack
        with open(manifest_path) as stream:
            assert stream.read() == original


@pytest.mark.parametrize(
    "fields, expected",
    [
        ({"memory_performance_tier": 2}, 2),
        ({"memory_tier": 3}, 3),
        ({"memory_tier": 3, "memory_performance_tier": 2}, 3),
    ],
)
def test_subpack_memory_tier_normalization(fields, expected):
    original = dict(fields)
    record = SubpackRecord.model_validate({"folder_name": "default", **fields})
    assert record.memory_tier == expected
    assert "memory_performance_tier" not in record.model_dump()
    assert fields == original


@pytest.mark.parametrize("field", ["memory_tier", "memory_performance_tier"])
def test_subpack_rejects_negative_memory_tiers(field):
    with pytest.raises(ValidationError):
        SubpackRecord.model_validate({"folder_name": "default", field: -1})
