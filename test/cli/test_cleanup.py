import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from bedrock_server_manager.cli import cleanup


class TestCleanup(unittest.TestCase):
    def test_cleanup_no_options(self):
        runner = CliRunner()
        result = runner.invoke(cleanup.cleanup)
        self.assertIn("No cleanup options specified", result.output)

    @patch("bedrock_server_manager.cli.cleanup._cleanup_pycache", return_value=1)
    def test_cleanup_cache(self, mock_cleanup_pycache):
        runner = CliRunner()
        result = runner.invoke(cleanup.cleanup, ["--cache"])
        self.assertEqual(result.exit_code, 0)
        mock_cleanup_pycache.assert_called_once()

    @patch("bedrock_server_manager.cli.cleanup.get_settings_instance")
    def test_cleanup_logs(self, mock_get_settings):
        runner = CliRunner()
        with runner.isolated_filesystem():
            log_dir = Path("logs")
            log_dir.mkdir()
            (log_dir / "log1.log.1").touch()
            time.sleep(0.1)
            (log_dir / "log2.log.2").touch()

            mock_get_settings.return_value.get.return_value = str(log_dir)

            result = runner.invoke(cleanup.cleanup, ["--logs"])

            self.assertEqual(result.exit_code, 0)
            self.assertTrue((log_dir / "log2.log.2").exists())
            self.assertFalse((log_dir / "log1.log.1").exists())

    @patch("bedrock_server_manager.cli.cleanup._cleanup_pycache", return_value=1)
    @patch("bedrock_server_manager.cli.cleanup.get_settings_instance")
    def test_cleanup_all(self, mock_get_settings, mock_cleanup_pycache):
        runner = CliRunner()
        with runner.isolated_filesystem():
            log_dir = Path("logs")
            log_dir.mkdir()
            (log_dir / "log1.log.1").touch()
            time.sleep(0.1)
            (log_dir / "log2.log.2").touch()
            mock_get_settings.return_value.get.return_value = str(log_dir)

            result = runner.invoke(cleanup.cleanup, ["--cache", "--logs"])

            self.assertEqual(result.exit_code, 0)
            mock_cleanup_pycache.assert_called_once()
            self.assertFalse((log_dir / "log1.log.1").exists())
            self.assertTrue((log_dir / "log2.log.2").exists())

    def test_cleanup_log_dir_override(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            log_dir = Path("custom_logs")
            log_dir.mkdir()
            (log_dir / "log1.log.1").touch()
            time.sleep(0.1)
            (log_dir / "log2.log.2").touch()

            result = runner.invoke(
                cleanup.cleanup, ["--logs", "--log-dir", str(log_dir)]
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue((log_dir / "log2.log.2").exists())
            self.assertFalse((log_dir / "log1.log.1").exists())
