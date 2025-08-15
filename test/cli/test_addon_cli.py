import unittest
from unittest.mock import patch
from click.testing import CliRunner
from bedrock_server_manager.cli import addon


class TestAddon(unittest.TestCase):
    @patch("bedrock_server_manager.cli.addon.addon_api.import_addon")
    def test_install_addon_with_file(self, mock_import_addon):
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("test.mcpack", "w") as f:
                f.write("test")

            result = runner.invoke(
                addon.install_addon,
                ["--server", "test-server", "--file", "test.mcpack"],
            )

            self.assertEqual(result.exit_code, 0)
            mock_import_addon.assert_called_once()

    @patch("bedrock_server_manager.cli.addon.api_application.list_available_addons_api")
    @patch("bedrock_server_manager.cli.addon.questionary.select")
    @patch("bedrock_server_manager.cli.addon.addon_api.import_addon")
    def test_install_addon_interactive(
        self, mock_import_addon, mock_select, mock_list_addons
    ):
        mock_list_addons.return_value = {
            "files": ["/path/to/addon1.mcpack", "/path/to/addon2.mcaddon"]
        }
        mock_select.return_value.ask.return_value = "addon1.mcpack"
        runner = CliRunner()
        result = runner.invoke(addon.install_addon, ["--server", "test-server"])

        self.assertEqual(result.exit_code, 0)
        mock_import_addon.assert_called_once()

    @patch("bedrock_server_manager.cli.addon.api_application.list_available_addons_api")
    @patch("bedrock_server_manager.cli.addon.questionary.select")
    @patch("bedrock_server_manager.cli.addon.addon_api.import_addon")
    def test_install_addon_interactive_cancel(
        self, mock_import_addon, mock_select, mock_list_addons
    ):
        mock_list_addons.return_value = {"files": ["/path/to/addon1.mcpack"]}
        mock_select.return_value.ask.return_value = "Cancel"
        runner = CliRunner()
        result = runner.invoke(addon.install_addon, ["--server", "test-server"])

        self.assertIn("Addon installation cancelled", result.output)
        mock_import_addon.assert_not_called()

    @patch("bedrock_server_manager.cli.addon.api_application.list_available_addons_api")
    def test_install_addon_no_addons(self, mock_list_addons):
        mock_list_addons.return_value = {"files": []}
        runner = CliRunner()
        result = runner.invoke(addon.install_addon, ["--server", "test-server"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No addon files found", result.output)
