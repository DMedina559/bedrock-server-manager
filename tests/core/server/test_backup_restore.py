import os
import zipfile


async def test_server_backup_directory(real_bedrock_server, app_context):
    """Test generating the server backup directory."""
    server = real_bedrock_server
    expected_dir = os.path.join(
        app_context.settings.get("paths.backups"), server.server_name
    )
    assert server.backups.server_backup_directory == expected_dir


async def test_backup_all_data(real_bedrock_server):
    """Test full backup creation."""
    server = real_bedrock_server

    # Create dummy world
    world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("dummy_data")

    # Set properties and config
    with open(server.paths.server_properties_path, "w") as f:
        f.write("level-name=test_world\n")
    with open(server.paths.allowlist_json_path, "w") as f:
        f.write("[]")
    with open(server.paths.permissions_json_path, "w") as f:
        f.write("[]")

    result = await server.backups.backup_all_data()

    assert result is not None
    assert "world" in result
    assert "server.properties" in result
    assert "allowlist.json" in result
    assert "permissions.json" in result
    assert result["world"] is not None
    assert result["server.properties"] is not None

    assert os.path.exists(result["world"])
    assert os.path.exists(result["server.properties"])

    # Verify zip content
    with zipfile.ZipFile(result["world"], "r") as zf:
        names = zf.namelist()
        # the zip structure depends on how shutil.make_archive creates it, typically rooted at dir
        assert any(n.endswith("level.dat") for n in names)


async def test_list_backups(real_bedrock_server):
    """Test listing created backups."""
    server = real_bedrock_server

    world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("dummy_data")

    with open(server.paths.server_properties_path, "w") as f:
        f.write("level-name=test_world\n")
    with open(server.paths.allowlist_json_path, "w") as f:
        f.write("[]")
    with open(server.paths.permissions_json_path, "w") as f:
        f.write("[]")

    await server.backups.backup_all_data()
    await server.backups.backup_all_data()  # Create two sets

    # `list_backups("all")` returns a dictionary of lists: {'world': [...], 'config': [...]}
    backups = await server.backups.list_backups(backup_type="all")

    assert "world_backups" in backups
    assert "properties_backups" in backups
    assert len(backups["world_backups"]) == 2


async def test_prune_server_backups(real_bedrock_server, app_context):
    """Test pruning old backups based on retention settings."""
    server = real_bedrock_server

    await app_context.settings.set("retention.backups", 1)

    world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("dummy_data")

    with open(server.paths.server_properties_path, "w") as f:
        f.write("level-name=test_world\n")
    with open(server.paths.allowlist_json_path, "w") as f:
        f.write("[]")
    with open(server.paths.permissions_json_path, "w") as f:
        f.write("[]")

    await server.backups.backup_all_data()
    await server.backups.backup_all_data()
    await server.backups.backup_all_data()

    await server.backups.prune_server_backups("test_world_backup_", "mcworld")
    await server.backups.prune_server_backups("server_backup_", "properties")

    backups = await server.backups.list_backups(backup_type="all")
    assert len(backups["world_backups"]) == 1
    assert len(backups["properties_backups"]) == 1
    assert len(backups["allowlist_backups"]) == 1
    assert len(backups["permissions_backups"]) == 1


async def test_restore_all_data_from_latest(real_bedrock_server):
    """Test restoring from the latest backup."""
    server = real_bedrock_server

    # Setup initial state
    world_dir = os.path.join(server.paths.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("original_data")
    with open(server.paths.server_properties_path, "w") as f:
        f.write("level-name=test_world\n")

    # Create backup
    await server.backups.backup_all_data()

    # Modify state
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("modified_data")

    # Restore
    result = await server.backups.restore_all_data_from_latest()

    assert result is not None
    assert "world" in result
    assert "server.properties" in result

    # Verify original state restored
    with open(os.path.join(world_dir, "level.dat"), "r") as f:
        assert f.read() == "original_data"


async def test_rapid_config_backups_keep_newest_contents(real_bedrock_server):
    from pathlib import Path

    server = real_bedrock_server
    await server.settings.set("retention.backups", 2)
    original = Path(server.paths.server_properties_path)
    original.write_text("level-name=first\n")
    first = await server.backups.backup_config("server.properties")
    original.write_text("level-name=second\n")
    # Even a deliberately old source mtime must not make the new backup older.
    os.utime(original, (1, 1))
    second = await server.backups.backup_config("server.properties")
    assert first != second
    files = await server.backups.list_backups("properties")
    assert files[0] == second
    await server.settings.set("retention.backups", 1)
    await server.backups.prune_server_backups("server_backup_", "properties")
    assert not Path(first).exists()
    await server.backups.restore_config(second)
    assert original.read_text() == "level-name=second\n"


async def test_legacy_config_backup_restores(real_bedrock_server):
    from pathlib import Path

    server = real_bedrock_server
    directory = Path(server.backups.server_backup_directory)
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / "server_backup_20250101_120000.properties"
    backup.write_text("level-name=legacy\n")
    await server.backups.restore_config(str(backup))
    assert await server.get_world_name() == "legacy"


async def test_restore_config_rejects_running_server(real_bedrock_server):
    import pytest

    from bedrock_server_manager.error import BackupRestoreError

    server = real_bedrock_server
    backup = await server.backups.backup_config("server.properties")
    await server.start()
    with pytest.raises(BackupRestoreError):
        await server.backups.restore_config(backup)
    assert await server.is_running()


async def test_restore_properties_selects_backed_up_world(populated_server):
    from pathlib import Path

    server = populated_server
    backed_up_world = await server.get_world_name()
    world = Path(server.paths.server_dir) / "worlds" / backed_up_world
    marker = world / "restoration.txt"
    marker.write_text("original")
    await server.backups.backup_all_data()
    marker.write_text("changed")
    await server.properties.set_server_property("level-name", "other_world")
    await server.backups.restore_all_data_from_latest()
    assert await server.get_world_name() == backed_up_world
    assert marker.read_text() == "original"
