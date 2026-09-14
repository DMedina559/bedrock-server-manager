import os
from unittest.mock import patch

import pytest
from bsm_test_utils.addons import create_mcworld


def test_extract_mcworld(real_bedrock_server, tmp_path, valid_mcworld_zip):
    """Test extracting a .mcworld file."""
    server = real_bedrock_server

    zip_path = valid_mcworld_zip

    extract_dir = tmp_path / "extracted_world"
    server.extract_mcworld(str(zip_path), str(extract_dir))

    assert os.path.exists(extract_dir)
    assert os.path.exists(os.path.join(extract_dir, "level.dat"))


def test_export_world(real_bedrock_server, tmp_path):
    """Test exporting a world."""
    server = real_bedrock_server

    world_dir = os.path.join(server.server_dir, "worlds")
    os.makedirs(world_dir, exist_ok=True)

    # create_mcworld signature: (target_dir, name, level_dat_content, packs)
    # create_mcworld natively creates a zip with a .mcworld extension
    # So we'll create the mcworld file, then extract it into the worlds directory
    world_zip_path = create_mcworld(str(tmp_path), name="test_world")

    world_path = os.path.join(world_dir, "test_world")
    os.makedirs(world_path, exist_ok=True)
    import zipfile

    with zipfile.ZipFile(world_zip_path, "r") as zf:
        zf.extractall(world_path)

    export_target = os.path.join(str(tmp_path), "exported_world.mcworld")
    server.export_world("test_world", export_target)

    assert os.path.exists(export_target)
    assert export_target.endswith(".mcworld")


def test_delete_world(real_bedrock_server):
    """Test deleting the active world."""
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)

    assert os.path.exists(world_dir)
    with patch.object(server, "get_world_name", return_value="test_world"):
        assert server.delete_world() is True

    assert not os.path.exists(world_dir)


def test_import_world(real_bedrock_server, tmp_path, valid_mcworld_zip):
    """Test importing a world from a zip/mcworld file."""
    server = real_bedrock_server

    zip_path = valid_mcworld_zip

    with patch.object(server, "get_world_name", return_value="test_world"):
        world_name = server.import_world(str(zip_path))

    assert world_name == "test_world"

    # valid_mcworld_zip uses "Test World" so the extracted directory might be differently named,
    # but import_world copies it under the target world name or the zip name.
    # We'll just verify the level.dat exists in the imported directory
    expected_world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    assert os.path.exists(expected_world_dir)
    assert os.path.exists(os.path.join(expected_world_dir, "level.dat"))


def test_import_world_invalid(real_bedrock_server, tmp_path):
    """Test importing an invalid world fails."""
    server = real_bedrock_server

    invalid_path = tmp_path / "invalid.mcworld"
    invalid_path.write_text("not a zip")

    from bedrock_server_manager.error import BackupRestoreError

    with pytest.raises(BackupRestoreError):
        server.import_world(str(invalid_path))
