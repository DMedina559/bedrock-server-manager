import unittest
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from questionary import ValidationError

from bedrock_server_manager.cli import utils


class TestUtils(unittest.TestCase):
    def test_handle_api_response_success(self):
        response = {
            "status": "success",
            "message": "Test success",
            "data": {"key": "value"},
        }
        result = utils.handle_api_response(response, "Default success")
        self.assertEqual(result, {"key": "value"})

    def test_handle_api_response_error(self):
        response = {"status": "error", "message": "Test error"}
        with self.assertRaises(click.Abort):
            utils.handle_api_response(response, "Default success")

    @patch("platform.system", return_value="Linux")
    def test_linux_only_on_linux(self, mock_system):
        @utils.linux_only
        def dummy_command():
            return "OK"

        self.assertEqual(dummy_command(), "OK")

    @patch("platform.system", return_value="Windows")
    def test_linux_only_on_windows(self, mock_system):
        @utils.linux_only
        def dummy_command():
            return "OK"

        with self.assertRaises(click.Abort):
            dummy_command()

    @patch("bedrock_server_manager.api.utils.validate_server_name_format")
    def test_server_name_validator_success(self, mock_validate):
        mock_validate.return_value = {"status": "success"}
        validator = utils.ServerNameValidator()
        document = MagicMock()
        document.text = "valid-server"
        validator.validate(document)

    @patch("bedrock_server_manager.api.utils.validate_server_name_format")
    def test_server_name_validator_error(self, mock_validate):
        mock_validate.return_value = {"status": "error", "message": "Invalid name"}
        validator = utils.ServerNameValidator()
        document = MagicMock()
        document.text = "invalid-server"
        with self.assertRaises(ValidationError):
            validator.validate(document)

    @patch("bedrock_server_manager.api.utils.validate_server_exist")
    def test_server_exists_validator_success(self, mock_validate):
        mock_validate.return_value = {"status": "success"}
        validator = utils.ServerExistsValidator()
        document = MagicMock()
        document.text = "existing-server"
        validator.validate(document)

    @patch("bedrock_server_manager.api.utils.validate_server_exist")
    def test_server_exists_validator_error(self, mock_validate):
        mock_validate.return_value = {"status": "error", "message": "Server not found"}
        validator = utils.ServerExistsValidator()
        document = MagicMock()
        document.text = "non-existing-server"
        with self.assertRaises(ValidationError):
            validator.validate(document)

    @patch("questionary.select")
    @patch("bedrock_server_manager.api.application.get_all_servers_data")
    def test_get_server_name_interactively_select(self, mock_get_servers, mock_select):
        mock_get_servers.return_value = {
            "data": {"servers": [{"name": "server1"}, {"name": "server2"}]}
        }
        mock_select.return_value.ask.return_value = "server1"
        result = utils.get_server_name_interactively()
        self.assertEqual(result, "server1")

    @patch("questionary.text")
    @patch("bedrock_server_manager.api.application.get_all_servers_data")
    def test_get_server_name_interactively_text(self, mock_get_servers, mock_text):
        mock_get_servers.return_value = {"data": {"servers": []}}
        mock_text.return_value.ask.return_value = "new-server"
        result = utils.get_server_name_interactively()
        self.assertEqual(result, "new-server")

    @patch(
        "bedrock_server_manager.api.server_install_config.validate_server_property_value"
    )
    def test_property_validator_success(self, mock_validate):
        mock_validate.return_value = {"status": "success"}
        validator = utils.PropertyValidator("level-name")
        document = MagicMock()
        document.text = "MyWorld"
        validator.validate(document)

    @patch(
        "bedrock_server_manager.api.server_install_config.validate_server_property_value"
    )
    def test_property_validator_error(self, mock_validate):
        mock_validate.return_value = {
            "status": "error",
            "message": "Invalid level name",
        }
        validator = utils.PropertyValidator("level-name")
        document = MagicMock()
        document.text = "Invalid World!"
        with self.assertRaises(ValidationError):
            validator.validate(document)

    @patch("click.echo")
    def test_print_server_table(self, mock_echo):
        servers = [
            {"name": "server1", "status": "RUNNING", "version": "1.19.0"},
            {"name": "server2", "status": "STOPPED", "version": "1.18.2"},
        ]
        utils._print_server_table(servers)

        # Build a string of all calls to mock_echo
        output = "".join(str(call_args) for call_args in mock_echo.call_args_list)

        self.assertIn("server1", output)
        self.assertIn("RUNNING", output)
        self.assertIn("1.19.0", output)
        self.assertIn("server2", output)
        self.assertIn("STOPPED", output)
        self.assertIn("1.18.2", output)

    @patch("bedrock_server_manager.cli.utils.api_application.get_all_servers_data")
    def test_list_servers(self, mock_get_all_servers_data):
        mock_get_all_servers_data.return_value = {
            "data": {
                "servers": [
                    {"name": "server1", "status": "RUNNING", "version": "1.19.0"},
                    {"name": "server2", "status": "STOPPED", "version": "1.18.2"},
                ]
            }
        }
        runner = CliRunner()
        result = runner.invoke(utils.list_servers)
        self.assertIn("server1", result.output)
        self.assertIn("server2", result.output)
        self.assertEqual(result.exit_code, 0)
