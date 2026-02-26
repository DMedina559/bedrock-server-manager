import json
import os
import zipfile

import pytest

from bedrock_server_manager.error import (
    AppFileNotFoundError,
    ExtractError,
    UserInputError,
)


def test_list_world_addons(real_bedrock_server):
    server = real_bedrock_server

    # Create dummy addons
    world_dir = os.path.join(server.server_dir, "worlds", "world")
    os.makedirs(os.path.join(world_dir, "resource_packs", "rp1_folder"), exist_ok=True)
    with open(
        os.path.join(world_dir, "resource_packs", "rp1_folder", "manifest.json"), "w"
    ) as f:
        json.dump(
            {
                "header": {"name": "rp1", "uuid": "rp1_uuid", "version": [1, 0, 0]},
                "modules": [{"type": "resources"}],
            },
            f,
        )

    with open(os.path.join(world_dir, "world_resource_packs.json"), "w") as f:
        json.dump([{"pack_id": "rp1_uuid", "version": [1, 0, 0]}], f)

    addons = server.list_world_addons()

    assert len(addons["resource_packs"]) == 1
    assert addons["resource_packs"][0]["uuid"] == "rp1_uuid"
    assert addons["resource_packs"][0]["status"] == "ACTIVE"


def test_process_addon_file(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds", "world")
    os.makedirs(world_dir, exist_ok=True)

    # Create a dummy addon file
    addon_path = tmp_path / "test_addon.mcpack"
    with zipfile.ZipFile(addon_path, "w") as zf:
        zf.writestr(
            "manifest.json",
            '{"header": {"name": "test addon", "uuid": "rp1", "version": [1,0,0]}, "modules": [{"type": "resources"}]}',
        )

    server.process_addon_file(str(addon_path))

    assert len(server.list_world_addons()["resource_packs"]) == 1


def test_process_addon_file_unsupported_type(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    unsupported_path = tmp_path / "test.txt"
    unsupported_path.write_text("test")
    with pytest.raises(UserInputError):
        server.process_addon_file(str(unsupported_path))


def test_process_mcaddon_archive_invalid_zip(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    invalid_zip_path = tmp_path / "invalid.mcaddon"
    invalid_zip_path.write_text("not a zip")
    with pytest.raises(ExtractError):
        server._process_mcaddon_archive(str(invalid_zip_path))


def test_install_pack_from_extracted_data_missing_manifest(
    real_bedrock_server, tmp_path
):
    server = real_bedrock_server
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    with pytest.raises(AppFileNotFoundError):
        server._install_pack_from_extracted_data(str(pack_dir), "dummy.mcpack")


def test_remove_addon_not_found(real_bedrock_server):
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds", "world")
    os.makedirs(world_dir, exist_ok=True)
    # No exception should be raised
    server.remove_addon("non_existent_uuid", "resource")


def test_export_addon_not_found(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds", "world")
    os.makedirs(world_dir, exist_ok=True)
    with pytest.raises(AppFileNotFoundError):
        server.export_addon("non_existent_uuid", "resource", str(tmp_path))


def test_remove_addon(real_bedrock_server):
    server = real_bedrock_server

    # Create dummy addons
    world_dir = os.path.join(server.server_dir, "worlds", "world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "world_resource_packs.json"), "w") as f:
        json.dump([{"pack_id": "rp1", "version": [1, 0, 0]}], f)

    addon_dir = os.path.join(
        server.server_dir,
        "worlds",
        "world",
        "resource_packs",
        "test_addon_1.0.0",
    )
    os.makedirs(addon_dir)
    with open(os.path.join(addon_dir, "manifest.json"), "w") as f:
        json.dump(
            {
                "header": {"name": "test_addon", "uuid": "rp1", "version": [1, 0, 0]},
                "modules": [{"type": "resources"}],
            },
            f,
        )

    server.remove_addon("rp1", "resource")

    assert not os.path.exists(addon_dir)

    with open(os.path.join(world_dir, "world_resource_packs.json"), "r") as f:
        data = json.load(f)
        assert len(data) == 0


def test_process_mcaddon_with_folders(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds", "world")
    os.makedirs(world_dir, exist_ok=True)

    # 1. Create a temporary structure for the addon
    # addon_root/
    #   behavior/
    #     manifest.json
    #   resource/
    #     manifest.json

    addon_build_dir = tmp_path / "addon_build"
    addon_build_dir.mkdir()

    bp_dir = addon_build_dir / "behavior"
    bp_dir.mkdir()
    with open(bp_dir / "manifest.json", "w") as f:
        json.dump(
            {
                "header": {"name": "bp1", "uuid": "bp1_uuid", "version": [1, 0, 0]},
                "modules": [{"type": "data"}],
            },
            f,
        )

    rp_dir = addon_build_dir / "resource"
    rp_dir.mkdir()
    with open(rp_dir / "manifest.json", "w") as f:
        json.dump(
            {
                "header": {"name": "rp1", "uuid": "rp1_uuid", "version": [1, 0, 0]},
                "modules": [{"type": "resources"}],
            },
            f,
        )

    # 2. Zip it into an .mcaddon file
    mcaddon_path = tmp_path / "folder_structure.mcaddon"
    with zipfile.ZipFile(mcaddon_path, "w") as zf:
        # Add behavior pack
        for root, _, files in os.walk(bp_dir):
            for file in files:
                zf.write(os.path.join(root, file), os.path.join("behavior", file))

        # Add resource pack
        for root, _, files in os.walk(rp_dir):
            for file in files:
                zf.write(os.path.join(root, file), os.path.join("resource", file))

    # 3. Process the addon file
    server.process_addon_file(str(mcaddon_path))

    # 4. Verify that packs are installed
    addons = server.list_world_addons()

    # Check behavior packs
    bps = [bp for bp in addons["behavior_packs"] if bp["uuid"] == "bp1_uuid"]
    assert len(bps) == 1, "Behavior pack not installed"
    assert bps[0]["status"] == "ACTIVE"

    # Check resource packs
    rps = [rp for rp in addons["resource_packs"] if rp["uuid"] == "rp1_uuid"]
    assert len(rps) == 1, "Resource pack not installed"
    assert rps[0]["status"] == "ACTIVE"


def test_process_addon_file_script_type(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds", "world")
    os.makedirs(world_dir, exist_ok=True)

    # Create a dummy addon file with script type
    addon_path = tmp_path / "test_script_addon.mcpack"
    with zipfile.ZipFile(addon_path, "w") as zf:
        zf.writestr(
            "manifest.json",
            '{"header": {"name": "test script addon", "uuid": "script_uuid", "version": [1,0,0]}, "modules": [{"type": "script"}]}',
        )

    # This should now succeed
    server.process_addon_file(str(addon_path))

    # Verify it is installed as a behavior pack
    addons = server.list_world_addons()
    bps = [bp for bp in addons["behavior_packs"] if bp["uuid"] == "script_uuid"]
    assert len(bps) == 1
    assert bps[0]["status"] == "ACTIVE"
