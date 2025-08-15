import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from bedrock_server_manager.cli.player import player


@pytest.fixture
def runner():
    return CliRunner()


def test_player_scan_success(runner):
    """Test the 'player scan' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.player.player_api.scan_and_update_player_db_api"
        ) as mock_scan,
        patch(
            "bedrock_server_manager.cli.player._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_scan.return_value = {"status": "success", "message": "Scan complete."}

        result = runner.invoke(player, ["scan"])

        assert result.exit_code == 0
        mock_scan.assert_called_once()
        mock_handle_response.assert_called_once_with(
            mock_scan.return_value, "Player database updated successfully."
        )


def test_player_add_success(runner):
    """Test the 'player add' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.player.player_api.add_players_manually_api"
        ) as mock_add,
        patch(
            "bedrock_server_manager.cli.player._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_add.return_value = {"status": "success", "message": "Players added."}

        result = runner.invoke(player, ["add", "-p", "TestPlayer:12345"])

        assert result.exit_code == 0
        mock_add.assert_called_once_with(["TestPlayer:12345"])
        mock_handle_response.assert_called_once_with(
            mock_add.return_value, "Players added/updated successfully."
        )


def test_player_scan_failure(runner):
    """Test the 'player scan' command with a failed API response."""
    with (
        patch(
            "bedrock_server_manager.cli.player.player_api.scan_and_update_player_db_api"
        ) as mock_scan,
        patch(
            "bedrock_server_manager.cli.player._handle_api_response"
        ) as mock_handle_response,
    ):
        from bedrock_server_manager.error import BSMError

        mock_scan.side_effect = BSMError("Scan failed.")

        result = runner.invoke(player, ["scan"])

        assert result.exit_code != 0
        assert "An error occurred during scan: Scan failed." in result.output
        mock_handle_response.assert_not_called()


def test_player_add_failure(runner):
    """Test the 'player add' command with a failed API response."""
    with (
        patch(
            "bedrock_server_manager.cli.player.player_api.add_players_manually_api"
        ) as mock_add,
        patch(
            "bedrock_server_manager.cli.player._handle_api_response"
        ) as mock_handle_response,
    ):
        from bedrock_server_manager.error import BSMError

        mock_add.side_effect = BSMError("Add failed.")

        result = runner.invoke(player, ["add", "-p", "TestPlayer:12345"])

        assert result.exit_code != 0
        assert "An error occurred while adding players: Add failed." in result.output
        mock_handle_response.assert_not_called()


def test_player_add_no_players(runner):
    """Test the 'player add' command with no players specified."""
    result = runner.invoke(player, ["add"])

    assert result.exit_code != 0
    assert "Missing option" in result.output
