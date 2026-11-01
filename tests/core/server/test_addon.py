import json
import os
import shutil
from unittest.mock import patch

import pytest
from bsm_test_utils import create_behavior_pack, create_resource_pack
from pydantic import ValidationError

from bedrock_server_manager.api.models.addon import ListInstalledAddonsResponse
from bedrock_server_manager.core.data import SubpackRecord


async def test_addon_lifecycle_and_subpack_listing(real_bedrock_server):
    """Test listing, enabling, disabling, reordering, subpack extensions, and removing addons."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        bp_dir = os.path.join(world_dir, "behavior_packs")
        rp_dir = os.path.join(world_dir, "resource_packs")
        os.makedirs(bp_dir, exist_ok=True)
        os.makedirs(rp_dir, exist_ok=True)

        bp1_path = create_behavior_pack(bp_dir, name="bp1", as_zip=False)
        bp2_path = create_behavior_pack(bp_dir, name="bp2", as_zip=False)
        rp_path = create_resource_pack(rp_dir, name="rp1", as_zip=False)

        with open(os.path.join(bp1_path, "manifest.json")) as f:
            bp1_uuid = json.load(f)["header"]["uuid"]
        with open(os.path.join(bp2_path, "manifest.json")) as f:
            bp2_uuid = json.load(f)["header"]["uuid"]
        with open(os.path.join(rp_path, "manifest.json")) as f:
            rp_uuid = json.load(f)["header"]["uuid"]

        addons = await server.addons.list_installed_addons()
        assert len(addons["behavior_packs"]) == 2
        assert len(addons["resource_packs"]) == 1
        assert {p["uuid"] for p in addons["behavior_packs"]} == {bp1_uuid, bp2_uuid}
        assert addons["resource_packs"][0]["uuid"] == rp_uuid

        # Enable and Disable
        await server.addons.enable_addon(bp1_uuid, "behavior")
        bp_json_path = os.path.join(world_dir, "world_behavior_packs.json")
        assert os.path.exists(bp_json_path)
        with open(bp_json_path) as f:
            data = json.load(f)
            assert len(data) == 1 and data[0]["pack_id"] == bp1_uuid

        addons = await server.addons.list_installed_addons()
        bp1_entry = next(p for p in addons["behavior_packs"] if p["uuid"] == bp1_uuid)
        assert bp1_entry["status"] == "ACTIVE"

        await server.addons.disable_addon(bp1_uuid, "behavior")
        with open(bp_json_path) as f:
            assert json.load(f) == []
        addons = await server.addons.list_installed_addons()
        bp1_entry = next(p for p in addons["behavior_packs"] if p["uuid"] == bp1_uuid)
        assert bp1_entry["status"] == "INACTIVE"

        # Reorder enabled addons
        await server.addons.enable_addon(bp1_uuid, "behavior")
        await server.addons.enable_addon(bp2_uuid, "behavior")
        await server.addons.reorder_addons([bp2_uuid, bp1_uuid], "behavior")
        with open(bp_json_path) as f:
            data = json.load(f)
            assert [d["pack_id"] for d in data] == [bp2_uuid, bp1_uuid]

        # Remove addons
        await server.addons.remove_addon(bp1_uuid, "behavior")
        await server.addons.remove_addon(bp2_uuid, "behavior")
        addons = await server.addons.list_installed_addons()
        assert len(addons["behavior_packs"]) == 0
        with open(bp_json_path) as f:
            assert json.load(f) == []

        # Subpack manifest extensions (with and without extra pack)
        subpack_path = create_resource_pack(rp_dir, name="subpacks", as_zip=False)
        manifest_path = os.path.join(subpack_path, "manifest.json")
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

        addons = await server.addons.list_installed_addons()
        response = ListInstalledAddonsResponse.model_validate(
            {"status": "success", "addons": addons}
        )
        pack = next(p for p in response.addons.resource_packs if p.subpacks)
        assert [p.memory_tier for p in pack.subpacks] == list(range(5))
        assert len(response.addons.resource_packs) == 2
        with open(manifest_path) as stream:
            assert stream.read() == original


async def test_process_mcpack_archives(real_bedrock_server, tmp_path):
    """Test processing valid and corrupt .mcpack archives."""
    server = real_bedrock_server

    with patch.object(server, "get_world_name", return_value="test_world"):
        world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
        os.makedirs(world_dir, exist_ok=True)

        # Invalid mcpack first
        bad_zip = create_behavior_pack(
            str(tmp_path), name="test_invalid_pack", as_zip=True, invalid_json=True
        )
        bad_mcpack = tmp_path / "test_invalid_pack.mcpack"
        shutil.move(str(bad_zip), str(bad_mcpack))
        try:
            await server.addons.process_addon_file(str(bad_mcpack))
        except Exception:
            pass
        addons = await server.addons.list_installed_addons()
        assert len(addons.get("behavior_packs", [])) == 0

        # Valid mcpack
        zip_path = create_behavior_pack(str(tmp_path), name="test_pack", as_zip=True)
        mcpack_path = tmp_path / "test_pack.mcpack"
        shutil.move(str(zip_path), str(mcpack_path))
        await server.addons.process_addon_file(str(mcpack_path))
        addons = await server.addons.list_installed_addons()
        assert len(addons["behavior_packs"]) == 1
        assert addons["behavior_packs"][0]["status"] == "ACTIVE"


def test_subpack_memory_tier_validation():
    for fields, expected in [
        ({"memory_performance_tier": 2}, 2),
        ({"memory_tier": 3}, 3),
        ({"memory_tier": 3, "memory_performance_tier": 2}, 3),
    ]:
        original = dict(fields)
        record = SubpackRecord.model_validate({"folder_name": "default", **fields})
        assert record.memory_tier == expected
        assert "memory_performance_tier" not in record.model_dump()
        assert fields == original

    for field in ("memory_tier", "memory_performance_tier"):
        with pytest.raises(ValidationError):
            SubpackRecord.model_validate({"folder_name": "default", field: -1})
