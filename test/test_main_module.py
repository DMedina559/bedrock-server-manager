import pytest
from unittest.mock import patch
from click.testing import CliRunner
from bedrock_server_manager.__main__ import create_cli_app

cli = create_cli_app()


@pytest.fixture
def runner():
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


@patch("bedrock_server_manager.__main__.setup_logging")
@patch("bedrock_server_manager.__main__.startup_checks")
def test_main_no_args(mock_startup_checks, mock_setup_logging, runner):
    """Test that the main function runs without arguments."""
    result = runner.invoke(cli)
    assert result.exit_code != 0


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
