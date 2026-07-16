import os
import zipfile
from unittest.mock import patch

import pytest


def test_extract_mcworld(real_bedrock_server, tmp_path):
    """Test extracting a .mcworld file."""
    server = real_bedrock_server

    zip_path = tmp_path / "test.mcworld"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("level.dat", b"dummy level data")

    extract_dir = tmp_path / "extracted_world"
    server.extract_mcworld(str(zip_path), str(extract_dir))

    assert os.path.exists(extract_dir)
    assert os.path.exists(os.path.join(extract_dir, "level.dat"))


def test_export_world(real_bedrock_server, tmp_path):
    """Test exporting a world."""
    server = real_bedrock_server

    world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("dummy_data")

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


def test_import_world(real_bedrock_server, tmp_path):
    """Test importing a world from a zip/mcworld file."""
    server = real_bedrock_server

    zip_path = tmp_path / "test_world.mcworld"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("level.dat", b"dummy level data")

    with patch.object(server, "get_world_name", return_value="test_world"):
        world_name = server.import_world(str(zip_path))

    assert world_name == "test_world"

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
