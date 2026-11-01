import os
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bsm_test_utils.addons import create_mcworld

from bedrock_server_manager.error import BackupRestoreError, SendCommandError


async def test_world_extract_export_import_and_delete(
    real_bedrock_server, tmp_path, valid_mcworld_zip
):
    """Test extracting, offline exporting, importing (valid & invalid), and deleting worlds."""
    server = real_bedrock_server
    zip_path = valid_mcworld_zip

    # Extract mcworld
    extract_dir = tmp_path / "extracted_world"
    await server.worlds.extract_mcworld(str(zip_path), str(extract_dir))
    assert os.path.exists(extract_dir)
    assert os.path.exists(os.path.join(extract_dir, "level.dat"))

    # Export world offline
    world_dir = os.path.join(server.paths.server_dir, "worlds")
    os.makedirs(world_dir, exist_ok=True)
    world_zip_path = create_mcworld(str(tmp_path), name="test_world")
    world_path = os.path.join(world_dir, "test_world")
    os.makedirs(world_path, exist_ok=True)
    with zipfile.ZipFile(world_zip_path, "r") as zf:
        zf.extractall(world_path)

    export_target = os.path.join(str(tmp_path), "exported_world.mcworld")
    await server.worlds.export_world("test_world", export_target)
    assert os.path.exists(export_target) and export_target.endswith(".mcworld")

    # Delete world
    await server.properties.set_server_property("level-name", "test_world")
    assert await server.worlds.delete_world() is True
    assert not os.path.exists(world_path)

    # Import valid world
    world_name = await server.worlds.import_world(str(zip_path))
    assert world_name == "test_world"
    assert os.path.exists(os.path.join(world_path, "level.dat"))

    # Import invalid world
    invalid_path = tmp_path / "invalid.mcworld"
    invalid_path.write_text("not a zip")
    with pytest.raises(BackupRestoreError):
        await server.worlds.import_world(str(invalid_path))


async def test_live_export_world_and_error_handling(
    real_bedrock_server, tmp_path, monkeypatch
):
    """Test live world export using save hold/query/resume, timeout, and resume error handling."""
    server = real_bedrock_server
    world_dir = os.path.join(server.paths.server_dir, "worlds")
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

    log_file = server.paths.server_log_path
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
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
        await server.worlds.export_world("test_world", export_target)

    assert os.path.exists(export_target)
    assert ["save hold", "save query", "save resume"] == [
        c for c in sent_commands if c in ("save hold", "save query", "save resume")
    ][:3]

    await server.worlds.extract_mcworld(export_target, "extracted_live")
    ext_dir = os.path.join(server.paths.server_dir, "worlds", "extracted_live")
    assert os.path.getsize(os.path.join(ext_dir, "db", "000001.ldb")) == 20
    assert os.path.getsize(os.path.join(ext_dir, "level.dat")) == 15
    assert os.path.getsize(os.path.join(ext_dir, "world_icon.jpeg")) == 30

    # Timeout still executes save resume
    sent_commands.clear()
    server.send_command = AsyncMock(side_effect=lambda cmd: sent_commands.append(cmd))
    timeout_target = os.path.join(str(tmp_path), "timeout_export.mcworld")
    with pytest.raises(BackupRestoreError):
        await server.worlds._live_export_world(
            "test_world", timeout_target, poll_interval=0.01, timeout=0.05
        )
    assert "save hold" in sent_commands
    assert "save query" in sent_commands
    assert "save resume" in sent_commands

    # Resume failure preserves primary error (query_succeeds False and True)
    world = Path(server.paths.server_dir) / "worlds" / "resume_world"
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"level-data")
    log = Path(server.paths.server_log_path)

    for query_succeeds in (False, True):
        log.write_text("", encoding="utf-8")
        target = tmp_path / f"resume_{query_succeeds}.mcworld"
        commands = []

        async def send_command(command, qs=query_succeeds, cmds=commands):
            cmds.append(command)
            if command == "save resume":
                raise SendCommandError("command channel unavailable")
            if command == "save query" and qs:
                with log.open("a", encoding="utf-8") as output:
                    output.write(
                        "Data saved. Files are now ready to be copied.\n"
                        "resume_world/level.dat:5\n"
                    )

        with monkeypatch.context() as fault:
            fault.setattr(server, "send_command", send_command)
            with pytest.raises(BackupRestoreError) as failure:
                await server.worlds._live_export_world(
                    "resume_world", str(target), poll_interval=0.01, timeout=0.05
                )
        assert "save resume" in commands
        if query_succeeds:
            assert target.is_file()
            assert "could not be resumed" in str(failure.value)
            assert isinstance(failure.value.__cause__, SendCommandError)
        else:
            assert not target.exists()
            assert "Timed out" in str(failure.value)
            assert "Resuming server saves also failed" in failure.value.__notes__[0]
