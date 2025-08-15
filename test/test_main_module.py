import pytest
from unittest.mock import patch
from click.testing import CliRunner
from bedrock_server_manager.__main__ import cli


@pytest.fixture
def runner():
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


@patch("bedrock_server_manager.__main__.setup_logging")
@patch("bedrock_server_manager.__main__.startup_checks")
@patch("bedrock_server_manager.cli.main_menus.main_menu")
def test_main_no_args(mock_main_menu, mock_startup_checks, mock_setup_logging, runner):
    """Test that the main function runs without arguments."""
    result = runner.invoke(cli)
    assert result.exit_code == 0
    mock_main_menu.assert_called_once()


@patch("bedrock_server_manager.__main__.setup_logging")
@patch("bedrock_server_manager.__main__.startup_checks")
@patch("bedrock_server_manager.api.web.start_web_server_api")
def test_main_web_command(
    mock_start_web_server, mock_startup_checks, mock_setup_logging, runner
):
    """Test that the web command calls the start_web_server_api function."""
    runner.invoke(cli, ["web", "start"])
    mock_start_web_server.assert_called_once()


@patch("bedrock_server_manager.__main__.setup_logging")
@patch("bedrock_server_manager.__main__.startup_checks")
def test_main_generate_password_command(
    mock_startup_checks, mock_setup_logging, runner
):
    """Test that the generate-password command calls the generate_password_hash_command function."""
    with patch(
        "bedrock_server_manager.cli.generate_password.click.prompt"
    ) as mock_prompt:
        mock_prompt.return_value = "testpassword"
        result = runner.invoke(cli, ["generate-password"])
        assert result.exit_code == 0
        assert "Hash generated successfully" in result.output


@patch("bedrock_server_manager.__main__.setup_logging")
@patch("bedrock_server_manager.__main__.startup_checks")
def test_plugin_cli_command(mock_startup_checks, mock_setup_logging, runner):
    """Test that plugin CLI commands are added to the CLI."""
    import click
    from bedrock_server_manager.__main__ import cli, _add_plugin_cli_commands
    from unittest.mock import MagicMock

    @click.command("test-command")
    def test_command():
        print("test command")

    mock_plugin_manager = MagicMock()
    mock_plugin_manager.plugin_cli_commands = [test_command]

    _add_plugin_cli_commands(cli, mock_plugin_manager)

    result = runner.invoke(cli, ["test-command"])
    assert result.exit_code == 0
    assert "test command" in result.output
