import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from bedrock_server_manager.cli.server_allowlist import allowlist


@pytest.fixture
def runner():
    return CliRunner()


def test_allowlist_add_success(runner):
    """Test the 'allowlist add' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_allowlist.config_api.add_players_to_allowlist_api"
        ) as mock_add,
        patch(
            "bedrock_server_manager.cli.server_allowlist._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_add.return_value = {"status": "success", "data": {"added_count": 1}}

        result = runner.invoke(
            allowlist, ["add", "-s", "test-server", "-p", "TestPlayer"]
        )

        assert result.exit_code == 0
        mock_add.assert_called_once_with(
            "test-server", [{"name": "TestPlayer", "ignoresPlayerLimit": False}]
        )
        mock_handle_response.assert_called_once()


def test_allowlist_add_failure(runner):
    """Test the 'allowlist add' command with a failed API response."""
    with patch(
        "bedrock_server_manager.cli.server_allowlist.config_api.add_players_to_allowlist_api"
    ) as mock_add:
        from bedrock_server_manager.error import BSMError

        mock_add.side_effect = BSMError("Add failed.")

        result = runner.invoke(
            allowlist, ["add", "-s", "test-server", "-p", "TestPlayer"]
        )

        assert result.exit_code != 0
        assert "An error occurred: Add failed." in result.output


def test_allowlist_remove_success(runner):
    """Test the 'allowlist remove' command with a successful API response."""
    with patch(
        "bedrock_server_manager.cli.server_allowlist.config_api.remove_players_from_allowlist"
    ) as mock_remove:
        mock_remove.return_value = {
            "status": "success",
            "details": {"removed": ["TestPlayer"], "not_found": []},
        }

        result = runner.invoke(
            allowlist, ["remove", "-s", "test-server", "-p", "TestPlayer"]
        )

        assert result.exit_code == 0
        mock_remove.assert_called_once_with("test-server", ["TestPlayer"])
        assert "Successfully removed 1 player(s)" in result.output


def test_allowlist_remove_not_found(runner):
    """Test the 'allowlist remove' command when a player is not found."""
    with patch(
        "bedrock_server_manager.cli.server_allowlist.config_api.remove_players_from_allowlist"
    ) as mock_remove:
        mock_remove.return_value = {
            "status": "success",
            "details": {"removed": [], "not_found": ["NotFoundPlayer"]},
        }

        result = runner.invoke(
            allowlist, ["remove", "-s", "test-server", "-p", "NotFoundPlayer"]
        )

        assert result.exit_code == 0
        assert "1 player(s) were not found" in result.output


def test_allowlist_list_success(runner):
    """Test the 'allowlist list' command with a successful API response."""
    with patch(
        "bedrock_server_manager.cli.server_allowlist.config_api.get_server_allowlist_api"
    ) as mock_get:
        mock_get.return_value = {
            "status": "success",
            "players": [{"name": "TestPlayer", "ignoresPlayerLimit": False}],
        }

        result = runner.invoke(allowlist, ["list", "-s", "test-server"])

        assert result.exit_code == 0
        mock_get.assert_called_once_with("test-server")
        assert "TestPlayer" in result.output


def test_allowlist_list_empty(runner):
    """Test the 'allowlist list' command when the allowlist is empty."""
    with patch(
        "bedrock_server_manager.cli.server_allowlist.config_api.get_server_allowlist_api"
    ) as mock_get:
        mock_get.return_value = {"status": "success", "players": []}

        result = runner.invoke(allowlist, ["list", "-s", "test-server"])

        assert result.exit_code == 0
        assert "allowlist for server 'test-server' is empty" in result.output


def test_interactive_allowlist_workflow(runner):
    """Test the interactive allowlist workflow."""
    with (
        patch(
            "bedrock_server_manager.cli.server_allowlist.config_api.get_server_allowlist_api"
        ) as mock_get,
        patch("questionary.text") as mock_text,
        patch("questionary.confirm") as mock_confirm,
        patch(
            "bedrock_server_manager.cli.server_allowlist.config_api.add_players_to_allowlist_api"
        ) as mock_add,
    ):
        mock_get.return_value = {"status": "success", "players": []}
        mock_text.return_value.ask.side_effect = ["NewPlayer", ""]
        mock_confirm.return_value.ask.return_value = True
        mock_add.return_value = {"status": "success"}

        result = runner.invoke(allowlist, ["add", "-s", "test-server"])

        assert result.exit_code == 0
        mock_add.assert_called_once_with(
            "test-server", [{"name": "NewPlayer", "ignoresPlayerLimit": True}]
        )
