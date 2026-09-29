import os
import zipfile
from unittest.mock import AsyncMock, patch


async def test_server_backup_directory(real_bedrock_server, app_context):
    """Test generating the server backup directory."""
    server = real_bedrock_server
    expected_dir = os.path.join(
        app_context.settings.get("paths.backups"), server.server_name
    )
    assert server.server_backup_directory == expected_dir


async def test_backup_all_data(real_bedrock_server):
    """Test full backup creation."""
    server = real_bedrock_server

    # Create dummy world
    world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("dummy_data")

    # Set properties and config
    with open(server.server_properties_path, "w") as f:
        f.write("level-name=test_world\n")
    with open(server.allowlist_json_path, "w") as f:
        f.write("[]")
    with open(server.permissions_json_path, "w") as f:
        f.write("[]")

    with patch.object(
        server, "get_world_name", new_callable=AsyncMock, return_value="test_world"
    ):
        result = await server.backup_all_data()

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

    world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("dummy_data")

    with open(server.server_properties_path, "w") as f:
        f.write("level-name=test_world\n")
    with open(server.allowlist_json_path, "w") as f:
        f.write("[]")
    with open(server.permissions_json_path, "w") as f:
        f.write("[]")

    with patch.object(
        server, "get_world_name", new_callable=AsyncMock, return_value="test_world"
    ):
        import asyncio

        await server.backup_all_data()
        await asyncio.sleep(1)
        await server.backup_all_data()  # Create two sets

    # `list_backups("all")` returns a dictionary of lists: {'world': [...], 'config': [...]}
    backups = await server.list_backups(backup_type="all")

    assert "world_backups" in backups
    assert "properties_backups" in backups
    assert len(backups["world_backups"]) == 2


async def test_prune_server_backups(real_bedrock_server, app_context):
    """Test pruning old backups based on retention settings."""
    server = real_bedrock_server

    await app_context.settings.set("retention.backups", 1)

    world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("dummy_data")

    with open(server.server_properties_path, "w") as f:
        f.write("level-name=test_world\n")
    with open(server.allowlist_json_path, "w") as f:
        f.write("[]")
    with open(server.permissions_json_path, "w") as f:
        f.write("[]")

    with patch.object(
        server, "get_world_name", new_callable=AsyncMock, return_value="test_world"
    ):
        import asyncio

        await server.backup_all_data()
        await asyncio.sleep(1)
        await server.backup_all_data()
        await asyncio.sleep(1)
        await server.backup_all_data()

    await server.prune_server_backups("test_world_backup_", "mcworld")
    await server.prune_server_backups("server_backup_", "properties")

    backups = await server.list_backups(backup_type="all")
    assert len(backups["world_backups"]) == 1
    assert len(backups["properties_backups"]) == 1
    assert len(backups["allowlist_backups"]) == 1
    assert len(backups["permissions_backups"]) == 1


async def test_restore_all_data_from_latest(real_bedrock_server):
    """Test restoring from the latest backup."""
    server = real_bedrock_server

    # Setup initial state
    world_dir = os.path.join(server.server_dir, "worlds", "test_world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("original_data")
    with open(server.server_properties_path, "w") as f:
        f.write("level-name=test_world\n")

    # Create backup
    with patch.object(
        server, "get_world_name", new_callable=AsyncMock, return_value="test_world"
    ):
        await server.backup_all_data()

    # Modify state
    with open(os.path.join(world_dir, "level.dat"), "w") as f:
        f.write("modified_data")

    # Restore
    result = await server.restore_all_data_from_latest()

    assert result is not None
    assert "world" in result
    assert "server.properties" in result

    # Verify original state restored
    with open(os.path.join(world_dir, "level.dat"), "r") as f:
        assert f.read() == "original_data"
