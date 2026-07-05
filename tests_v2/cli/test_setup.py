from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.setup import setup


@pytest.fixture
def runner():
    return CliRunner()


def test_setup_interactive_workflow(runner, app_context, monkeypatch):
    """Test interactive setup workflow successfully applies base configurations."""
    # Mock Questionary
    mock_questionary = MagicMock()
    # 1. data_dir prompt
    # 2. advance_db confirm (False)
    # 3. web_host
    # 4. web_port
    # 5. service config confirm (True)
    mock_questionary.text().ask.side_effect = ["/mocked/data/dir", "0.0.0.0", "12345"]
    mock_questionary.confirm().ask.side_effect = [False, True]
    monkeypatch.setattr(
        "bedrock_server_manager.cli.setup.questionary", mock_questionary
    )

    mock_workflow = MagicMock()
    monkeypatch.setattr(
        "bedrock_server_manager.cli.setup.interactive_web_service_workflow",
        mock_workflow,
    )

    # Mock bcm_config logic so it doesnt actually overwrite real state
    mock_bcm = MagicMock()
    mock_bcm.get_config_dir.return_value = "/mock/dir"
    mock_bcm.load_config.return_value = {}
    monkeypatch.setattr("bedrock_server_manager.cli.setup.bcm_config", mock_bcm)

    result = runner.invoke(setup, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Setup complete!" in result.output
    assert "Using the default SQLite database" in result.output

    mock_bcm.set_config_value.assert_called_with("data_dir", "/mocked/data/dir")
    assert app_context.settings.get("web.host") == "0.0.0.0"
    assert app_context.settings.get("web.port") == 12345
    mock_workflow.assert_called_once()


def test_setup_advanced_db(runner, app_context, monkeypatch):
    """Test setup workflow successfully configures advanced database values and overrides configs."""
    mock_questionary = MagicMock()
    # 1. data_dir
    # 2. advance_db confirm (True)
    # 3. DB Url
    # 4. web_host
    # 5. web_port
    # 6. service config confirm (False)
    mock_questionary.text().ask.side_effect = [
        "/mocked/data/dir",
        "postgresql://url",
        "1.2.3.4",
        "80",
    ]
    mock_questionary.confirm().ask.side_effect = [True, False]
    monkeypatch.setattr(
        "bedrock_server_manager.cli.setup.questionary", mock_questionary
    )

    mock_workflow = MagicMock()
    monkeypatch.setattr(
        "bedrock_server_manager.cli.setup.interactive_web_service_workflow",
        mock_workflow,
    )

    mock_bcm = MagicMock()
    mock_bcm.get_config_dir.return_value = "/mock/dir"
    mock_bcm.load_config.return_value = {}
    monkeypatch.setattr("bedrock_server_manager.cli.setup.bcm_config", mock_bcm)

    result = runner.invoke(setup, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Database URL set to: postgresql://url" in result.output
    assert "Skipping service configuration." in result.output

    mock_workflow.assert_not_called()
    assert app_context.settings.get("web.host") == "1.2.3.4"
    assert app_context.settings.get("web.port") == 80
