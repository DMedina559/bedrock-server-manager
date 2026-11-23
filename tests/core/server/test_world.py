import asyncio
import os
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bsm_test_utils import create_corrupt_archive, create_mcworld

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
    invalid_path = create_corrupt_archive(tmp_path, filename="invalid.mcworld")
    with pytest.raises(BackupRestoreError):
        await server.worlds.import_world(str(invalid_path))


@pytest.fixture
async def live_export_server(real_bedrock_server):
    server = real_bedrock_server
    await server.start()
    await asyncio.wait_for(server.process.run.ready_event.wait(), 5)
    return server


async def test_live_export_truncates_reported_files(live_export_server, tmp_path):
    server = live_export_server
    run = server.process.run
    world = Path(server.paths.server_dir) / "worlds" / "test_world"
    (world / "db").mkdir(parents=True)
    (world / "db" / "000001.ldb").write_bytes(b"X" * 100)
    (world / "level.dat").write_bytes(b"Y" * 50)
    (world / "world_icon.jpeg").write_bytes(b"Z" * 30)
    sent_commands = []

    async def mock_send_command(cmd):
        sent_commands.append(cmd)
        if cmd == "save query":
            run.feed(
                b"[2026-09-27 17:24:30:850 INFO] Data saved. Files are now ready to be copied.\n"
                b"test_world/db/000001.ldb:20, test_world/level.dat:15\n"
            )

    export_target = os.path.join(str(tmp_path), "live_exported_world.mcworld")

    with (
        patch.object(server, "send_command", side_effect=mock_send_command),
        patch.object(server, "is_running", new_callable=AsyncMock, return_value=True),
        patch.object(
            server, "get_world_name", new_callable=AsyncMock, return_value="test_world"
        ),
    ):
        await server.worlds.export_world("test_world", export_target)

    assert os.path.exists(export_target)
    assert sent_commands[0] == "save hold"
    assert sent_commands[-1] == "save resume"
    assert sent_commands.count("save query") >= 2

    await server.worlds.extract_mcworld(export_target, "extracted_live")
    ext_dir = os.path.join(server.paths.server_dir, "worlds", "extracted_live")
    assert os.path.getsize(os.path.join(ext_dir, "db", "000001.ldb")) == 20
    assert os.path.getsize(os.path.join(ext_dir, "level.dat")) == 15
    assert os.path.getsize(os.path.join(ext_dir, "world_icon.jpeg")) == 30


async def test_live_export_timeout_still_resumes_saves(live_export_server, tmp_path):
    server = live_export_server
    target = tmp_path / "timeout.mcworld"
    with patch.object(server, "send_command") as command:
        with pytest.raises(BackupRestoreError, match="Timed out"):
            await server.worlds._live_export_world(
                "test_world", str(target), poll_interval=0.01, timeout=0.05
            )
    sent = [call.args[0] for call in command.await_args_list]
    assert sent[0] == "save hold"
    assert "save query" in sent
    assert sent[-1] == "save resume"
    assert not target.exists()


@pytest.mark.parametrize("query_succeeds", [False, True])
async def test_live_export_resume_failure_preserves_outcome(
    live_export_server, tmp_path, query_succeeds
):
    server = live_export_server
    world = Path(server.paths.server_dir) / "worlds" / "resume_world"
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"level-data")
    target = tmp_path / "resume.mcworld"
    commands = []

    async def send_command(command):
        commands.append(command)
        if command == "save resume":
            raise SendCommandError("command channel unavailable")
        if command == "save query" and query_succeeds:
            server.process.run.feed(
                b"Data saved. Files are now ready to be copied.\n"
                b"resume_world/level.dat:5\n"
            )

    with patch.object(server, "send_command", side_effect=send_command):
        with pytest.raises(BackupRestoreError) as failure:
            await server.worlds._live_export_world(
                "resume_world", str(target), poll_interval=0.01, timeout=0.05
            )
    assert commands[-1] == "save resume"
    if query_succeeds:
        assert target.is_file()
        assert "could not be resumed" in str(failure.value)
        assert isinstance(failure.value.__cause__, SendCommandError)
    else:
        assert not target.exists()
        assert "Timed out" in str(failure.value)
        assert "Resuming server saves also failed" in failure.value.__notes__[0]
