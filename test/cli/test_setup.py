import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from bedrock_server_manager.cli.setup import setup
from bedrock_server_manager.config import bcm_config


@pytest.fixture
def runner():
    return CliRunner()


@patch("bedrock_server_manager.cli.setup.bcm_config")
@patch("bedrock_server_manager.cli.setup.questionary")
def test_setup_command_basic(mock_questionary, mock_bcm_config, runner):
    # Mock app_context and its settings
    mock_app_context = MagicMock()
    mock_settings = MagicMock()
    mock_app_context.settings = mock_settings

    # Mock bcm_config
    mock_bcm_config.load_config.return_value = {}

    # Mock questionary prompts
    mock_questionary.text.return_value.ask.side_effect = [
        "test_data_dir",  # Data directory
        "testhost",  # Web host
        "12345",  # Web port
    ]
    mock_questionary.confirm.return_value.ask.return_value = False  # No advanced DB

    result = runner.invoke(
        setup,
        obj={"app_context": mock_app_context, "bsm": MagicMock(), "cli": MagicMock()},
    )

    assert result.exit_code == 0
    assert "Setup complete!" in result.output

    # Verify config saving
    mock_bcm_config.set_config_value.assert_called_once_with(
        "data_dir", "test_data_dir"
    )

    # Verify settings saving
    mock_settings.set.assert_any_call("web.host", "testhost")
    mock_settings.set.assert_any_call("web.port", 12345)


@patch("bedrock_server_manager.cli.setup.bcm_config")
@patch("bedrock_server_manager.cli.setup.questionary")
def test_setup_command_advanced_db(mock_questionary, mock_bcm_config, runner):
    # Mock app_context and its settings
    mock_app_context = MagicMock()
    mock_settings = MagicMock()
    mock_app_context.settings = mock_settings

    # Mock bcm_config
    mock_bcm_config.load_config.return_value = {}

    # Mock questionary prompts
    mock_questionary.text.return_value.ask.side_effect = [
        "test_data_dir",
        "test_db_url",  # DB URL
        "testhost",
        "12345",
    ]
    mock_questionary.confirm.return_value.ask.side_effect = [
        True,
        False,
    ]  # Yes to advanced DB, No to service

    result = runner.invoke(
        setup,
        obj={"app_context": mock_app_context, "bsm": MagicMock(), "cli": MagicMock()},
    )

    assert result.exit_code == 0, result.output
    assert "Setup complete!" in result.output

    # Verify config saving
    mock_bcm_config.set_config_value.assert_any_call("data_dir", "test_data_dir")
    mock_bcm_config.set_config_value.assert_any_call("db_url", "test_db_url")

    # Verify settings saving
    mock_settings.set.assert_any_call("web.host", "testhost")
    mock_settings.set.assert_any_call("web.port", 12345)
