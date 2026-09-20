from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.api.install import install_new_server, update_server
from bedrock_server_manager.error import (
    BSMError,
    MissingArgumentError,
)


async def test_install_new_server_success(app_context, monkeypatch):
    """Test install_new_server formats new server context and runs successfully."""
    from unittest.mock import AsyncMock

    mock_server = MagicMock()
    mock_server.get_target_version = AsyncMock(return_value="LATEST")
    mock_server.get_version = AsyncMock(return_value="1.20")
    mock_server.is_update_needed = AsyncMock(return_value=True)
    mock_server.install_or_update = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.get_version = AsyncMock(return_value="1.20")
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await install_new_server("new_server", app_context)

    assert result["status"] == "success"
    assert result["version"] == "1.20"
    mock_server.install_or_update.assert_called_once_with(
        "LATEST", server_zip_path=None
    )


async def test_install_new_server_empty_name(app_context):
    """Test install_new_server rejects missing names."""
    with pytest.raises(MissingArgumentError):
        await install_new_server("", app_context)


async def test_install_new_server_already_exists(app_context, tmp_path):
    """Test install_new_server gracefully fails if server directory exists."""
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    (base_dir / "existing_server").mkdir()

    app_context.settings.set("paths.servers", str(base_dir))

    result = await install_new_server("existing_server", app_context)
    assert result["status"] == "error"
    assert "already exists" in result["message"]


async def test_install_new_server_no_base_dir(app_context):
    """Test install_new_server triggers error if path properties missing."""
    app_context.settings.set("paths.servers", None)

    result = await install_new_server("new_server", app_context)
    assert result["status"] == "error"
    assert "not configured in settings" in result["message"]


async def test_install_new_server_error(app_context, monkeypatch):
    """Test install_new_server traps underlying BSMError thrown via the class."""
    from unittest.mock import AsyncMock

    mock_server = MagicMock()
    mock_server.get_target_version = AsyncMock(return_value="LATEST")
    mock_server.get_version = AsyncMock(return_value="1.20")
    mock_server.is_update_needed = AsyncMock(return_value=True)
    mock_server.install_or_update = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.install_or_update.side_effect = BSMError("Broken install")
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await install_new_server("new_server", app_context)
    assert result["status"] == "error"
    assert "Broken install" in result["message"]


async def test_update_server_no_update_needed(app_context, monkeypatch):
    """Test update_server returns early if version is current."""
    from unittest.mock import AsyncMock

    mock_server = MagicMock()
    mock_server.get_target_version = AsyncMock(return_value="LATEST")
    mock_server.get_version = AsyncMock(return_value="1.20")
    mock_server.is_update_needed = AsyncMock(return_value=True)
    mock_server.install_or_update = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.is_update_needed = AsyncMock(return_value=False)
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await update_server("test_server", app_context)

    assert result["status"] == "success"
    assert result["updated"] is False
    assert "already up-to-date" in result["message"]


async def test_update_server_success(app_context, monkeypatch):
    """Test update_server triggers backups, locks, and lifecycle managers properly."""
    from unittest.mock import AsyncMock

    mock_server = AsyncMock()
    mock_server.get_target_version = AsyncMock(return_value="LATEST")
    mock_server.get_version = AsyncMock(return_value="1.20")
    mock_server.is_update_needed = AsyncMock(return_value=True)
    mock_server.install_or_update = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.is_update_needed = AsyncMock(return_value=True)
    mock_server.get_version = AsyncMock(return_value="1.21")
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Needs to bypass stop/start errors gracefully for test scope
    import contextlib

    @contextlib.asynccontextmanager
    async def mock_slm(*args, **kwargs):
        yield

    monkeypatch.setattr(
        "bedrock_server_manager.api.install.server_lifecycle_manager", mock_slm
    )

    result = await update_server("test_server", app_context)

    assert result["status"] == "success"
    assert result["updated"] is True
    assert result["new_version"] == "1.21"

    mock_server.backup_all_data.assert_called_once()
    mock_server.install_or_update.assert_called_once()


async def test_update_server_locked(app_context, monkeypatch):
    """Test update_server safely skips requests when lock is blocked."""
    from unittest.mock import AsyncMock

    mock_lock = MagicMock()
    import asyncio

    mock_lock.acquire = AsyncMock(side_effect=asyncio.TimeoutError())
    monkeypatch.setattr(
        "bedrock_server_manager.api.install._install_update_lock", mock_lock
    )

    result = await update_server("test_server", app_context)

    assert result["status"] == "skipped"
    assert "already in progress" in result["message"]


async def test_update_server_missing_name(app_context):
    """Test update_server checks bad incoming parameters."""
    result = await update_server("", app_context)
    assert result["status"] == "error"
    assert "cannot be empty" in result["message"]


async def test_update_server_error(app_context, monkeypatch):
    """Test update_server captures failing tasks from subclass appropriately."""
    from unittest.mock import AsyncMock

    mock_server = AsyncMock()
    mock_server.get_target_version = AsyncMock(return_value="LATEST")
    mock_server.get_version = AsyncMock(return_value="1.20")
    mock_server.is_update_needed = AsyncMock(return_value=True)
    mock_server.install_or_update = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.backup_all_data = AsyncMock()
    mock_server.is_update_needed = AsyncMock(return_value=True)
    mock_server.backup_all_data = AsyncMock(side_effect=BSMError("Backup Failed"))
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    import contextlib

    @contextlib.asynccontextmanager
    async def mock_slm(*args, **kwargs):
        yield

    monkeypatch.setattr(
        "bedrock_server_manager.api.install.server_lifecycle_manager", mock_slm
    )

    result = await update_server("test_server", app_context)

    assert result["status"] == "error"
    assert "Server update failed: Backup Failed" in result["message"]
