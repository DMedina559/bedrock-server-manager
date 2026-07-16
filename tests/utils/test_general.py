import os

import pytest

from bedrock_server_manager.error import AppFileNotFoundError, FileOperationError
from bedrock_server_manager.utils.general import (
    get_timestamp,
    list_content_files,
    startup_checks,
)


def test_startup_checks_creates_dirs(app_context, tmp_path):
    """Test startup_checks creates missing essential app directories."""
    app_context.settings.set("paths.servers", str(tmp_path / "servers"))
    app_context.settings.set("paths.content", str(tmp_path / "content"))
    app_context.settings.set("paths.downloads", str(tmp_path / "downloads"))
    app_context.settings.set("paths.plugins", str(tmp_path / "plugins"))
    app_context.settings.set("paths.backups", str(tmp_path / "backups"))
    app_context.settings.set("paths.logs", str(tmp_path / "logs"))

    startup_checks(app_context)

    assert os.path.isdir(tmp_path / "servers")
    assert os.path.isdir(tmp_path / "content")
    assert os.path.isdir(tmp_path / "content" / "worlds")
    assert os.path.isdir(tmp_path / "content" / "addons")
    assert os.path.isdir(tmp_path / "downloads")
    assert os.path.isdir(tmp_path / "plugins")
    assert os.path.isdir(tmp_path / "backups")
    assert os.path.isdir(tmp_path / "logs")


def test_startup_checks_handles_existing_dirs(app_context, tmp_path):
    """Test startup_checks gracefully handles existing directories without raising an error."""
    # Create the servers dir beforehand
    servers_dir = tmp_path / "servers"
    servers_dir.mkdir()

    app_context.settings.set("paths.servers", str(servers_dir))

    startup_checks(app_context)

    # Still exists and no crash
    assert os.path.isdir(servers_dir)


def test_startup_checks_python_version_fail(app_context, monkeypatch):
    """Test startup_checks raises a RuntimeError if the python version is unsupported."""
    from collections import namedtuple

    VersionInfo = namedtuple("VersionInfo", ["major", "minor", "micro"])
    monkeypatch.setattr("sys.version_info", VersionInfo(3, 9, 0))

    with pytest.raises(RuntimeError) as exc_info:
        startup_checks(app_context)
    assert "Python version 3.11 or later is required" in str(exc_info.value)


def test_get_timestamp():
    """Test get_timestamp generates a valid date string format."""
    timestamp = get_timestamp()
    assert isinstance(timestamp, str)
    assert len(timestamp) == 15  # YYYYMMDD_HHMMSS
    assert timestamp[8] == "_"


def test_list_content_files_success(tmp_path):
    """Test list_content_files correctly retrieves valid matches."""
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir()

    (worlds_dir / "world1.mcworld").touch()
    (worlds_dir / "world2.mcworld").touch()
    (worlds_dir / "ignore_this.txt").touch()

    result = list_content_files(str(tmp_path), "worlds", [".mcworld"])

    assert len(result) == 2
    assert any("world1.mcworld" in f for f in result)
    assert any("world2.mcworld" in f for f in result)
    assert not any("ignore_this.txt" in f for f in result)


def test_list_content_files_no_matches(tmp_path):
    """Test list_content_files returns empty when no files match."""
    addons_dir = tmp_path / "addons"
    addons_dir.mkdir()

    (addons_dir / "file.txt").touch()

    result = list_content_files(str(tmp_path), "addons", [".mcpack"])
    assert result == []


def test_list_content_files_subfolder_not_exist(tmp_path):
    """Test list_content_files returns empty if the target subfolder doesn't exist."""
    result = list_content_files(str(tmp_path), "missing_folder", [".txt"])
    assert result == []


def test_list_content_files_content_dir_missing():
    """Test list_content_files raises AppFileNotFoundError if missing a content directory."""
    with pytest.raises(AppFileNotFoundError) as exc_info:
        list_content_files("/does/not/exist/ever", "worlds", [".mcworld"])
    assert "not found at path:" in str(exc_info.value)


def test_list_content_files_os_error(tmp_path, monkeypatch):
    """Test list_content_files catches OS errors and raises a FileOperationError."""
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir()

    def mock_find_files(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr(
        "bedrock_server_manager.utils.general.find_files", mock_find_files
    )

    with pytest.raises(FileOperationError) as exc_info:
        list_content_files(str(tmp_path), "worlds", [".mcworld"])
    assert "Error scanning content directory" in str(exc_info.value)
