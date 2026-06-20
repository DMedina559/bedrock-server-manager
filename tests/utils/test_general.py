import os
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from bedrock_server_manager.utils.general import get_timestamp, startup_checks


class TestStartupChecks:
    def test_startup_checks_create_dirs(self, tmp_path):
        """Tests that startup_checks creates the necessary directories."""
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default=None: {
            "paths.servers": str(tmp_path / "servers"),
            "paths.content": str(tmp_path / "content"),
            "paths.downloads": str(tmp_path / "downloads"),
            "paths.plugins": str(tmp_path / "plugins"),
            "paths.backups": str(tmp_path / "backups"),
            "paths.logs": str(tmp_path / "logs"),
        }.get(key, default)

        mock_app_context = MagicMock()
        mock_app_context.settings = mock_settings

        startup_checks(mock_app_context)
        assert os.path.isdir(tmp_path / "servers")
        assert os.path.isdir(tmp_path / "content")
        assert os.path.isdir(tmp_path / "content" / "worlds")
        assert os.path.isdir(tmp_path / "content" / "addons")
        assert os.path.isdir(tmp_path / "downloads")
        assert os.path.isdir(tmp_path / "plugins")
        assert os.path.isdir(tmp_path / "backups")
        assert os.path.isdir(tmp_path / "logs")

    def test_startup_checks_dirs_exist(self, tmp_path):
        """Tests that startup_checks doesn't fail if directories already exist."""
        (tmp_path / "servers").mkdir()

        mock_settings = MagicMock()
        mock_settings.get.return_value = str(tmp_path / "servers")
        mock_app_context = MagicMock()
        mock_app_context.settings = mock_settings

        startup_checks(mock_app_context)
        assert os.path.isdir(tmp_path / "servers")

    def test_startup_checks_python_version_fail(self):
        """Tests that startup_checks raises an error for unsupported Python versions."""
        VersionInfo = namedtuple("VersionInfo", ["major", "minor", "micro"])
        mock_app_context = MagicMock()
        with patch("sys.version_info", VersionInfo(3, 9, 0)):
            with pytest.raises(RuntimeError):
                startup_checks(mock_app_context)


class TestGetTimestamp:
    def test_get_timestamp_format(self):
        """Tests that get_timestamp returns a string in the correct format."""
        timestamp = get_timestamp()
        assert isinstance(timestamp, str)
        # A simple check for the format, not the exact value
        assert len(timestamp) == 15
        assert timestamp[8] == "_"


class TestListContentFiles:
    def test_list_content_files_success(self, tmp_path):
        """Test list_content_files successfully lists files."""
        from bedrock_server_manager.utils import list_content_files

        worlds_dir = tmp_path / "worlds"
        worlds_dir.mkdir()
        (worlds_dir / "world1.mcworld").touch()
        (worlds_dir / "world2.mcworld").touch()
        (worlds_dir / "other.txt").touch()

        result = list_content_files(str(tmp_path), "worlds", [".mcworld"])
        assert len(result) == 2
        assert any("world1.mcworld" in f for f in result)
        assert any("world2.mcworld" in f for f in result)
        assert not any("other.txt" in f for f in result)

    def test_list_content_files_no_matches(self, tmp_path):
        """Test list_content_files when no files match extensions."""
        from bedrock_server_manager.utils import list_content_files

        addons_dir = tmp_path / "addons"
        addons_dir.mkdir()
        (addons_dir / "something.txt").touch()

        result = list_content_files(str(tmp_path), "addons", [".mcpack", ".mcaddon"])
        assert result == []

    def test_list_content_files_subfolder_not_exist(self, tmp_path):
        """Test list_content_files when the sub_folder does not exist."""
        from bedrock_server_manager.utils import list_content_files

        result = list_content_files(str(tmp_path), "non_existent_subfolder", [".txt"])
        assert result == []

    def test_list_content_files_main_content_dir_not_exist(self):
        """Test list_content_files raises AppFileNotFoundError if main content_dir is invalid."""
        from bedrock_server_manager.error import AppFileNotFoundError
        from bedrock_server_manager.utils import list_content_files

        with pytest.raises(AppFileNotFoundError, match="Content directory"):
            list_content_files(
                "/path/that/definitely/does/not/exist/12345", "worlds", [".mcworld"]
            )

    def test_list_content_files_os_error_on_glob(self, tmp_path, mocker):
        """Test list_content_files handles OSError from find_files."""
        from bedrock_server_manager.error import FileOperationError
        from bedrock_server_manager.utils import list_content_files

        worlds_dir = tmp_path / "worlds"
        worlds_dir.mkdir()

        mocker.patch(
            "bedrock_server_manager.utils.general.find_files",
            side_effect=OSError("Glob permission denied"),
        )

        with pytest.raises(
            FileOperationError, match="Error scanning content directory"
        ):
            list_content_files(str(tmp_path), "worlds", [".mcworld"])
