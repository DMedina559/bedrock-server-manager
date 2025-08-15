import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from bedrock_server_manager.cli.server_actions import server


@pytest.fixture
def runner():
    return CliRunner()


def test_server_start_success(runner):
    """Test the 'server start' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_actions.server_api.start_server"
        ) as mock_start,
        patch(
            "bedrock_server_manager.cli.server_actions._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_start.return_value = {"status": "success"}

        result = runner.invoke(server, ["start", "-s", "test-server"])

        assert result.exit_code == 0
        mock_start.assert_called_once_with("test-server", "detached")
        mock_handle_response.assert_called_once()


def test_server_stop_success(runner):
    """Test the 'server stop' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_actions.server_api.stop_server"
        ) as mock_stop,
        patch(
            "bedrock_server_manager.cli.server_actions._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_stop.return_value = {"status": "success"}

        result = runner.invoke(server, ["stop", "-s", "test-server"])

        assert result.exit_code == 0
        mock_stop.assert_called_once_with("test-server")
        mock_handle_response.assert_called_once()


def test_server_restart_success(runner):
    """Test the 'server restart' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_actions.server_api.restart_server"
        ) as mock_restart,
        patch(
            "bedrock_server_manager.cli.server_actions._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_restart.return_value = {"status": "success"}

        result = runner.invoke(server, ["restart", "-s", "test-server"])

        assert result.exit_code == 0
        mock_restart.assert_called_once_with("test-server")
        mock_handle_response.assert_called_once()


def test_server_delete_success(runner):
    """Test the 'server delete' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_actions.server_api.delete_server_data"
        ) as mock_delete,
        patch(
            "bedrock_server_manager.cli.server_actions._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_delete.return_value = {"status": "success"}

        result = runner.invoke(server, ["delete", "-s", "test-server", "-y"])

        assert result.exit_code == 0
        mock_delete.assert_called_once_with("test-server")
        mock_handle_response.assert_called_once()


def test_server_send_command_success(runner):
    """Test the 'server send-command' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_actions.server_api.send_command"
        ) as mock_send,
        patch(
            "bedrock_server_manager.cli.server_actions._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_send.return_value = {"status": "success"}

        result = runner.invoke(
            server, ["send-command", "-s", "test-server", "say", "hello"]
        )

        assert result.exit_code == 0
        mock_send.assert_called_once_with("test-server", "say hello")
        mock_handle_response.assert_called_once()


def test_server_config_success(runner):
    """Test the 'server config' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_actions.server_api.set_server_setting"
        ) as mock_set,
        patch(
            "bedrock_server_manager.cli.server_actions._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_set.return_value = {"status": "success"}

        result = runner.invoke(
            server, ["config", "-s", "test-server", "-k", "key", "-v", "value"]
        )

        assert result.exit_code == 0
        mock_set.assert_called_once_with("test-server", "key", "value")
        mock_handle_response.assert_called_once()


def test_server_start_failure(runner):
    """Test the 'server start' command with a failed API response."""
    with patch(
        "bedrock_server_manager.cli.server_actions.server_api.start_server"
    ) as mock_start:
        from bedrock_server_manager.error import BSMError

        mock_start.side_effect = BSMError("Start failed.")

        result = runner.invoke(server, ["start", "-s", "test-server"])

        assert result.exit_code != 0
        assert "Failed to start server: Start failed." in result.output


def test_server_delete_confirmation(runner):
    """Test the 'server delete' command confirmation prompt."""
    with patch(
        "bedrock_server_manager.cli.server_actions.server_api.delete_server_data"
    ) as mock_delete:
        result = runner.invoke(server, ["delete", "-s", "test-server"], input="n\n")

        assert result.exit_code != 0
        assert "Aborted!" in result.output
        mock_delete.assert_not_called()


def test_server_install_success(runner):
    """Test the 'server install' command with a successful API response."""
    with (
        patch("questionary.text") as mock_text,
        patch("questionary.confirm") as mock_confirm,
        patch(
            "bedrock_server_manager.cli.server_actions.config_api.install_new_server"
        ) as mock_install,
        patch(
            "bedrock_server_manager.cli.server_actions.interactive_properties_workflow"
        ),
        patch(
            "bedrock_server_manager.cli.server_actions.interactive_allowlist_workflow"
        ),
        patch(
            "bedrock_server_manager.cli.server_actions.interactive_permissions_workflow"
        ),
        patch("bedrock_server_manager.cli.server_actions.interactive_service_workflow"),
        patch("bedrock_server_manager.cli.server_actions.start_server"),
    ):
        mock_text.return_value.ask.side_effect = ["test-server", "LATEST"]
        mock_confirm.return_value.ask.return_value = False
        mock_install.return_value = {"status": "success", "version": "1.20.81.01"}

        result = runner.invoke(server, ["install"])

        assert result.exit_code == 0
        mock_install.assert_called_once_with("test-server", "LATEST", None)
