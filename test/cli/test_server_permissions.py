import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from bedrock_server_manager.cli.server_permissions import permissions


@pytest.fixture
def runner():
    return CliRunner()


def test_permissions_set_success(runner):
    """Test the 'permissions set' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_permissions.player_api.get_all_known_players_api"
        ) as mock_get_players,
        patch(
            "bedrock_server_manager.cli.server_permissions.config_api.configure_player_permission"
        ) as mock_set_perm,
        patch(
            "bedrock_server_manager.cli.server_permissions._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_get_players.return_value = {
            "players": [{"name": "TestPlayer", "xuid": "12345"}]
        }
        mock_set_perm.return_value = {"status": "success"}

        result = runner.invoke(
            permissions,
            ["set", "-s", "test-server", "-p", "TestPlayer", "-l", "operator"],
        )

        assert result.exit_code == 0
        mock_set_perm.assert_called_once_with(
            "test-server", "12345", "TestPlayer", "operator"
        )
        mock_handle_response.assert_called_once()


def test_permissions_set_player_not_found(runner):
    """Test the 'permissions set' command when the player is not found."""
    with patch(
        "bedrock_server_manager.cli.server_permissions.player_api.get_all_known_players_api"
    ) as mock_get_players:
        mock_get_players.return_value = {"players": []}

        result = runner.invoke(
            permissions,
            ["set", "-s", "test-server", "-p", "NotFoundPlayer", "-l", "operator"],
        )

        assert result.exit_code != 0
        assert "Player 'NotFoundPlayer' not found" in result.output


def test_permissions_list_success(runner):
    """Test the 'permissions list' command with a successful API response."""
    with patch(
        "bedrock_server_manager.cli.server_permissions.config_api.get_server_permissions_api"
    ) as mock_get_perms:
        mock_get_perms.return_value = {
            "status": "success",
            "data": {
                "permissions": [
                    {
                        "name": "TestPlayer",
                        "xuid": "12345",
                        "permission_level": "operator",
                    }
                ]
            },
        }

        result = runner.invoke(permissions, ["list", "-s", "test-server"])

        assert result.exit_code == 0
        mock_get_perms.assert_called_once_with("test-server")
        assert "TestPlayer" in result.output
        assert "Operator" in result.output


def test_permissions_list_empty(runner):
    """Test the 'permissions list' command when the permissions file is empty."""
    with patch(
        "bedrock_server_manager.cli.server_permissions.config_api.get_server_permissions_api"
    ) as mock_get_perms:
        mock_get_perms.return_value = {"status": "success", "data": {"permissions": []}}

        result = runner.invoke(permissions, ["list", "-s", "test-server"])

        assert result.exit_code == 0
        assert "permissions file for server 'test-server' is empty" in result.output


def test_interactive_permissions_workflow(runner):
    """Test the interactive permissions workflow."""
    with (
        patch(
            "bedrock_server_manager.cli.server_permissions.player_api.get_all_known_players_api"
        ) as mock_get_players,
        patch("questionary.select") as mock_select,
        patch(
            "bedrock_server_manager.cli.server_permissions.config_api.configure_player_permission"
        ) as mock_set_perm,
    ):
        mock_get_players.return_value = {
            "players": [{"name": "TestPlayer", "xuid": "12345"}]
        }
        mock_select.return_value.ask.side_effect = [
            "TestPlayer (XUID: 12345)",
            "operator",
            "Cancel",
        ]
        mock_set_perm.return_value = {"status": "success"}

        result = runner.invoke(permissions, ["set", "-s", "test-server"])

        assert result.exit_code == 0
        mock_set_perm.assert_called_once_with(
            "test-server", "12345", "TestPlayer", "operator"
        )
