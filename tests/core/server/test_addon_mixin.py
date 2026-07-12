import json
import os
import zipfile
from unittest.mock import patch


def setup_dummy_addon(server, pack_type, uuid, name, version=None):
    if version is None:
        version = [1, 0, 0]
    world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    pack_dir = "behavior_packs" if pack_type == "data" else "resource_packs"
    folder = os.path.join(world_dir, pack_dir, f"{name}_folder")
    os.makedirs(folder, exist_ok=True)

    with open(os.path.join(folder, "manifest.json"), "w") as f:
        json.dump(
            {
                "header": {"name": name, "uuid": uuid, "version": version},
                "modules": [{"type": pack_type}],
            },
            f,
        )
    return folder


def test_list_installed_addons(real_bedrock_server):
    """Test listing installed addons in physical folders."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        setup_dummy_addon(server, "data", "uuid-1", "bp1")
        setup_dummy_addon(server, "resources", "uuid-2", "rp1")

        addons = server.list_installed_addons()
        assert len(addons["behavior_packs"]) == 1
        assert len(addons["resource_packs"]) == 1
        assert addons["behavior_packs"][0]["uuid"] == "uuid-1"
        assert addons["resource_packs"][0]["uuid"] == "uuid-2"


def test_enable_disable_addon(real_bedrock_server):
    """Test enabling and disabling an addon."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        setup_dummy_addon(server, "data", "uuid-1", "bp1")

        # Test Enable
        server.enable_addon("uuid-1", "behavior")

        world_dir = os.path.join(server.server_dir, "worlds", "test_world")
        bp_json_path = os.path.join(world_dir, "world_behavior_packs.json")
        assert os.path.exists(bp_json_path)

        with open(bp_json_path, "r") as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["pack_id"] == "uuid-1"

        # Check list shows it as enabled (ACTIVE)
        addons = server.list_installed_addons()
        bp = addons["behavior_packs"][0]
        assert bp["status"] == "ACTIVE"

        # Test Disable
        server.disable_addon("uuid-1", "behavior")

        with open(bp_json_path, "r") as f:
            data = json.load(f)
            assert len(data) == 0

        # Check list shows it as disabled (INACTIVE)
        addons = server.list_installed_addons()
        bp = addons["behavior_packs"][0]
        assert bp["status"] == "INACTIVE"


def test_process_mcpack_archive(real_bedrock_server, tmp_path):
    """Test processing an mcpack file."""
    server = real_bedrock_server

    zip_path = tmp_path / "test.mcpack"
    with zipfile.ZipFile(zip_path, "w") as zf:
        manifest = {
            "header": {"name": "test_pack", "uuid": "uuid-123", "version": [1, 0, 0]},
            "modules": [{"type": "data"}],
        }
        zf.writestr("manifest.json", json.dumps(manifest))

    with patch.object(server, "get_world_name", return_value="test_world"):
        server.process_addon_file(str(zip_path))

        # Should be physically installed
        addons = server.list_installed_addons()
        assert len(addons["behavior_packs"]) == 1
        assert addons["behavior_packs"][0]["uuid"] == "uuid-123"
        assert (
            addons["behavior_packs"][0]["status"] == "ACTIVE"
        )  # Auto-enabled on install


def test_remove_addon(real_bedrock_server):
    """Test removing an addon deletes physical files and removes from active JSON."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        setup_dummy_addon(server, "data", "uuid-rem", "bp_rem")
        server.enable_addon("uuid-rem", "behavior")

        server.remove_addon("uuid-rem", "behavior")

        addons = server.list_installed_addons()
        assert len(addons["behavior_packs"]) == 0

        # Verify JSON is empty
        world_dir = os.path.join(server.server_dir, "worlds", "test_world")
        bp_json_path = os.path.join(world_dir, "world_behavior_packs.json")
        with open(bp_json_path, "r") as f:
            data = json.load(f)
            assert len(data) == 0


def test_reorder_addons(real_bedrock_server):
    """Test reordering enabled addons."""
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="test_world"):
        setup_dummy_addon(server, "data", "uuid-1", "bp1")
        setup_dummy_addon(server, "data", "uuid-2", "bp2")

        server.enable_addon("uuid-1", "behavior")
        server.enable_addon("uuid-2", "behavior")

        # Reorder sending uuid-2 first
        server.reorder_addons(["uuid-2", "uuid-1"], "behavior")

        world_dir = os.path.join(server.server_dir, "worlds", "test_world")
        bp_json_path = os.path.join(world_dir, "world_behavior_packs.json")
        with open(bp_json_path, "r") as f:
            data = json.load(f)
            assert data[0]["pack_id"] == "uuid-2"
            assert data[1]["pack_id"] == "uuid-1"
