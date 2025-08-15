import unittest
from unittest.mock import patch
from click.testing import CliRunner
from bedrock_server_manager.cli import backup_restore


class TestBackupRestore(unittest.TestCase):
    @patch("bedrock_server_manager.cli.backup_restore.backup_restore_api.backup_world")
    @patch(
        "bedrock_server_manager.cli.backup_restore.backup_restore_api.prune_old_backups"
    )
    def test_create_backup_world(self, mock_prune, mock_backup):
        runner = CliRunner()
        result = runner.invoke(
            backup_restore.create_backup,
            ["--server", "test-server", "--type", "world"],
        )
        self.assertEqual(result.exit_code, 0)
        mock_backup.assert_called_once_with("test-server", stop_start_server=True)
        mock_prune.assert_called_once_with(server_name="test-server")

    @patch(
        "bedrock_server_manager.cli.backup_restore.backup_restore_api.backup_config_file"
    )
    @patch(
        "bedrock_server_manager.cli.backup_restore.backup_restore_api.prune_old_backups"
    )
    def test_create_backup_config(self, mock_prune, mock_backup):
        runner = CliRunner()
        result = runner.invoke(
            backup_restore.create_backup,
            [
                "--server",
                "test-server",
                "--type",
                "config",
                "--file",
                "server.properties",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        mock_backup.assert_called_once_with(
            "test-server", "server.properties", stop_start_server=True
        )
        mock_prune.assert_called_once_with(server_name="test-server")

    @patch("bedrock_server_manager.cli.backup_restore.backup_restore_api.backup_all")
    @patch(
        "bedrock_server_manager.cli.backup_restore.backup_restore_api.prune_old_backups"
    )
    def test_create_backup_all(self, mock_prune, mock_backup):
        runner = CliRunner()
        result = runner.invoke(
            backup_restore.create_backup,
            ["--server", "test-server", "--type", "all"],
        )
        self.assertEqual(result.exit_code, 0)
        mock_backup.assert_called_once_with("test-server", stop_start_server=True)
        mock_prune.assert_called_once_with(server_name="test-server")

    @patch("bedrock_server_manager.cli.backup_restore._interactive_backup_menu")
    @patch("bedrock_server_manager.cli.backup_restore.backup_restore_api.backup_world")
    @patch(
        "bedrock_server_manager.cli.backup_restore.backup_restore_api.prune_old_backups"
    )
    def test_create_backup_interactive(self, mock_prune, mock_backup, mock_interactive):
        mock_interactive.return_value = ("world", None, True)
        runner = CliRunner()
        result = runner.invoke(
            backup_restore.create_backup, ["--server", "test-server"]
        )
        self.assertEqual(result.exit_code, 0)
        mock_interactive.assert_called_once_with("test-server")
        mock_backup.assert_called_once_with("test-server", stop_start_server=True)
        mock_prune.assert_called_once_with(server_name="test-server")

    @patch("bedrock_server_manager.cli.backup_restore.backup_restore_api.restore_world")
    def test_restore_backup_world(self, mock_restore):
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("world.mcworld", "w") as f:
                f.write("test")
            result = runner.invoke(
                backup_restore.restore_backup,
                ["--server", "test-server", "--file", "world.mcworld"],
            )
            self.assertEqual(result.exit_code, 0)
            mock_restore.assert_called_once()

    @patch(
        "bedrock_server_manager.cli.backup_restore.backup_restore_api.restore_config_file"
    )
    def test_restore_backup_config(self, mock_restore):
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("allowlist.json", "w") as f:
                f.write("test")

            result = runner.invoke(
                backup_restore.restore_backup,
                ["--server", "test-server", "--file", "allowlist.json"],
            )
            self.assertEqual(result.exit_code, 0)
            mock_restore.assert_called_once()

    @patch("bedrock_server_manager.cli.backup_restore._interactive_restore_menu")
    @patch("bedrock_server_manager.cli.backup_restore.backup_restore_api.restore_world")
    def test_restore_backup_interactive(self, mock_restore, mock_interactive):
        mock_interactive.return_value = ("world", "/path/to/backup.mcworld", True)
        runner = CliRunner()
        result = runner.invoke(
            backup_restore.restore_backup, ["--server", "test-server"]
        )
        self.assertEqual(result.exit_code, 0)
        mock_interactive.assert_called_once_with("test-server")
        mock_restore.assert_called_once_with(
            "test-server", "/path/to/backup.mcworld", stop_start_server=True
        )

    @patch(
        "bedrock_server_manager.cli.backup_restore.backup_restore_api.prune_old_backups"
    )
    def test_prune_backups(self, mock_prune):
        runner = CliRunner()
        result = runner.invoke(
            backup_restore.prune_backups, ["--server", "test-server"]
        )
        self.assertEqual(result.exit_code, 0)
        mock_prune.assert_called_once_with(server_name="test-server")
