import os
from unittest.mock import AsyncMock, patch

import pytest
from bsm_test_utils.addons import create_mcworld


async def test_extract_mcworld(real_bedrock_server, tmp_path, valid_mcworld_zip):
    """Test extracting a .mcworld file."""
    server = real_bedrock_server

    zip_path = valid_mcworld_zip

    extract_dir = tmp_path / "extracted_world"
    await server.extract_mcworld(str(zip_path), str(extract_dir))

    assert os.path.exists(extract_dir)
    assert os.path.exists(os.path.join(extract_dir, "level.dat"))


async def test_export_world(real_bedrock_server, tmp_path):
    """Test exporting a world offline."""
    server = real_bedrock_server

    world_dir = os.path.join(server.server_dir, "worlds")
    os.makedirs(world_dir, exist_ok=True)

    world_zip_path = create_mcworld(str(tmp_path), name="test_world")

    world_path = os.path.join(world_dir, "test_world")
    os.makedirs(world_path, exist_ok=True)
    import zipfile

    with zipfile.ZipFile(world_zip_path, "r") as zf:
        zf.extractall(world_path)

    export_target = os.path.join(str(tmp_path), "exported_world.mcworld")

    await server.export_world("test_world", export_target)

    assert os.path.exists(export_target)
    assert export_target.endswith(".mcworld")


async def test_live_export_world(real_bedrock_server, tmp_path):
    """Test live world export using save hold/query/resume."""
    server = real_bedrock_server

    world_dir = os.path.join(server.server_dir, "worlds")
    os.makedirs(world_dir, exist_ok=True)

    world_path = os.path.join(world_dir, "test_world")
    db_dir = os.path.join(world_path, "db")
    os.makedirs(db_dir, exist_ok=True)

    ldb_file = os.path.join(db_dir, "000001.ldb")
    level_dat = os.path.join(world_path, "level.dat")
    icon_file = os.path.join(world_path, "world_icon.jpeg")

    with open(ldb_file, "wb") as f:
        f.write(b"X" * 100)
    with open(level_dat, "wb") as f:
        f.write(b"Y" * 50)
    with open(icon_file, "wb") as f:
        f.write(b"Z" * 30)

    log_file = os.path.join(server.server_dir, "server_output.txt")
    server.server_log_path = log_file

    sent_commands = []

    async def mock_send_command(cmd):
        sent_commands.append(cmd)
        if cmd == "save query":
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(
                    "[2026-09-27 17:24:30:850 INFO] Data saved. Files are now ready to be copied.\n"
                    "test_world/db/000001.ldb:20, test_world/level.dat:15\n"
                )

    server.send_command = AsyncMock(side_effect=mock_send_command)

    export_target = os.path.join(str(tmp_path), "live_exported_world.mcworld")

    with (
        patch.object(server, "is_running", new_callable=AsyncMock, return_value=True),
        patch.object(
            server, "get_world_name", new_callable=AsyncMock, return_value="test_world"
        ),
    ):
        await server.export_world("test_world", export_target)

    assert os.path.exists(export_target)
    assert "save hold" in sent_commands
    assert "save query" in sent_commands
    assert "save resume" in sent_commands

    # Verify extracted mcworld contents and file truncation sizes
    await server.extract_mcworld(export_target, "extracted_live")

    ext_ldb = os.path.join(
        server.server_dir, "worlds", "extracted_live", "db", "000001.ldb"
    )
    ext_level_dat = os.path.join(
        server.server_dir, "worlds", "extracted_live", "level.dat"
    )
    ext_icon = os.path.join(
        server.server_dir, "worlds", "extracted_live", "world_icon.jpeg"
    )

    assert os.path.exists(ext_ldb)
    assert os.path.getsize(ext_ldb) == 20
    assert os.path.getsize(ext_level_dat) == 15
    assert os.path.getsize(ext_icon) == 30


async def test_live_export_world_finally_resume_on_timeout(
    real_bedrock_server, tmp_path
):
    """Test that save resume is executed in finally block even if save query times out."""
    server = real_bedrock_server

    world_dir = os.path.join(server.server_dir, "worlds")
    os.makedirs(world_dir, exist_ok=True)
    os.makedirs(os.path.join(world_dir, "test_world"), exist_ok=True)

    sent_commands = []

    async def mock_send_command(cmd):
        sent_commands.append(cmd)

    server.send_command = AsyncMock(side_effect=mock_send_command)
    export_target = os.path.join(str(tmp_path), "timeout_export.mcworld")

    from bedrock_server_manager.error import BackupRestoreError

    with pytest.raises(BackupRestoreError):
        await server._live_export_world(
            "test_world", export_target, poll_interval=0.01, timeout=0.05
        )

    assert "save hold" in sent_commands
    assert "save query" in sent_commands
    assert "save resume" in sent_commands


async def test_delete_world(real_bedrock_server):
    """Test deleting the active world."""
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)

    assert os.path.exists(world_dir)
    await server.set_server_property("level-name", "test_world")
    assert await server.delete_world() is True

    assert not os.path.exists(world_dir)


async def test_import_world(real_bedrock_server, tmp_path, valid_mcworld_zip):
    """Test importing a world from a zip/mcworld file."""
    server = real_bedrock_server

    zip_path = valid_mcworld_zip

    await server.set_server_property("level-name", "test_world")
    world_name = await server.import_world(str(zip_path))

    assert world_name == "test_world"

    # valid_mcworld_zip uses "Test World" so the extracted directory might be differently named,
    # but import_world copies it under the target world name or the zip name.
    # We'll just verify the level.dat exists in the imported directory
    expected_world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    assert os.path.exists(expected_world_dir)
    assert os.path.exists(os.path.join(expected_world_dir, "level.dat"))


async def test_import_world_invalid(real_bedrock_server, tmp_path):
    """Test importing an invalid world fails."""
    server = real_bedrock_server

    invalid_path = tmp_path / "invalid.mcworld"
    invalid_path.write_text("not a zip")

    from bedrock_server_manager.error import BackupRestoreError

    with pytest.raises(BackupRestoreError):
        await server.import_world(str(invalid_path))
