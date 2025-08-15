import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from bedrock_server_manager.cli.plugins import plugin


@pytest.fixture
def runner():
    return CliRunner()


def test_plugin_list_success(runner):
    """Test the 'plugin list' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.plugins.plugins_api.get_plugin_statuses"
        ) as mock_get_statuses,
        patch(
            "bedrock_server_manager.cli.plugins._print_plugin_table"
        ) as mock_print_table,
    ):
        mock_get_statuses.return_value = {
            "status": "success",
            "plugins": {"test-plugin": {"enabled": True, "version": "1.0"}},
        }

        result = runner.invoke(plugin, ["list"])

        assert result.exit_code == 0
        mock_get_statuses.assert_called_once()
        mock_print_table.assert_called_once_with(
            {"test-plugin": {"enabled": True, "version": "1.0"}}
        )


def test_plugin_enable_success(runner):
    """Test the 'plugin enable' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.plugins.plugins_api.set_plugin_status"
        ) as mock_set_status,
        patch(
            "bedrock_server_manager.cli.plugins._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_set_status.return_value = {"status": "success"}

        result = runner.invoke(plugin, ["enable", "test-plugin"])

        assert result.exit_code == 0
        mock_set_status.assert_called_once_with("test-plugin", True)
        mock_handle_response.assert_called_once()


def test_plugin_disable_success(runner):
    """Test the 'plugin disable' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.plugins.plugins_api.set_plugin_status"
        ) as mock_set_status,
        patch(
            "bedrock_server_manager.cli.plugins._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_set_status.return_value = {"status": "success"}

        result = runner.invoke(plugin, ["disable", "test-plugin"])

        assert result.exit_code == 0
        mock_set_status.assert_called_once_with("test-plugin", False)
        mock_handle_response.assert_called_once()


def test_plugin_reload_success(runner):
    """Test the 'plugin reload' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.plugins.plugins_api.reload_plugins"
        ) as mock_reload,
        patch(
            "bedrock_server_manager.cli.plugins._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_reload.return_value = {"status": "success"}

        result = runner.invoke(plugin, ["reload"])

        assert result.exit_code == 0
        mock_reload.assert_called_once()
        mock_handle_response.assert_called_once()


def test_plugin_trigger_event_success(runner):
    """Test the 'plugin trigger-event' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.plugins.plugins_api.trigger_external_plugin_event_api"
        ) as mock_trigger,
        patch(
            "bedrock_server_manager.cli.plugins._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_trigger.return_value = {"status": "success"}

        result = runner.invoke(plugin, ["trigger-event", "test-event"])

        assert result.exit_code == 0
        mock_trigger.assert_called_once_with("test-event", None)
        assert "Event 'test-event' triggered successfully." in result.output


def test_plugin_list_failure(runner):
    """Test the 'plugin list' command with a failed API response."""
    with patch(
        "bedrock_server_manager.cli.plugins.plugins_api.get_plugin_statuses"
    ) as mock_get_statuses:
        mock_get_statuses.return_value = {
            "status": "error",
            "message": "Failed to get statuses.",
        }

        result = runner.invoke(plugin, ["list"])

        assert result.exit_code != 0
        assert "Error: Failed to get statuses." in result.output
        mock_get_statuses.assert_called_once()


def test_plugin_enable_failure(runner):
    """Test the 'plugin enable' command with a failed API response."""
    with (
        patch(
            "bedrock_server_manager.cli.plugins.plugins_api.set_plugin_status"
        ) as mock_set_status,
        patch(
            "bedrock_server_manager.cli.plugins._handle_api_response"
        ) as mock_handle_response,
    ):
        from bedrock_server_manager.error import BSMError

        mock_set_status.side_effect = BSMError("Enable failed.")

        result = runner.invoke(plugin, ["enable", "test-plugin"])

        assert result.exit_code != 0
        assert "Failed to enable plugin 'test-plugin': Enable failed." in result.output
        mock_handle_response.assert_not_called()


def test_plugin_trigger_event_invalid_json(runner):
    """Test the 'plugin trigger-event' command with invalid JSON."""
    with patch(
        "bedrock_server_manager.cli.plugins.plugins_api.trigger_external_plugin_event_api"
    ) as mock_trigger:
        result = runner.invoke(
            plugin, ["trigger-event", "test-event", "--payload-json", "{'invalid-json"]
        )

        assert result.exit_code == 0
        assert "Error: Invalid JSON provided for payload" in result.output
        mock_trigger.assert_not_called()


def test_interactive_plugin_workflow_cancel(runner):
    """Test that the interactive plugin workflow handles user cancellation."""
    with (
        patch(
            "bedrock_server_manager.cli.plugins.plugins_api.get_plugin_statuses"
        ) as mock_get_statuses,
        patch("questionary.checkbox") as mock_checkbox,
    ):
        mock_get_statuses.return_value = {
            "status": "success",
            "plugins": {"test-plugin": {"enabled": False, "version": "1.0"}},
        }
        mock_checkbox.return_value.ask.return_value = None

        result = runner.invoke(plugin, [])

        assert result.exit_code == 0
        assert "Operation cancelled by user." in result.output
