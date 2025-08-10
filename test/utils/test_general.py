import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from collections import namedtuple

from bedrock_server_manager.utils.general import startup_checks, get_timestamp


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
