import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.setup import setup
from bedrock_server_manager.config import bcm_config


@pytest.fixture
def runner():
    return CliRunner()


def test_setup_interactive_workflow(
    runner, app_context, systemd, monkeypatch, tmp_path
):
    """Test interactive setup workflow successfully applies base configurations."""
    # Mock Questionary
    mock_questionary = MagicMock()
    # 1. data_dir prompt
    # 2. advance_db confirm (False)
    # 3. web_host
    # 4. web_port
    # 5. service config confirm (True)
    mock_questionary.text().ask.side_effect = [
        str(tmp_path / "configured_data"),
        "0.0.0.0",
        "12345",
    ]
    mock_questionary.confirm().ask.side_effect = [False, True, True, False, True]
    monkeypatch.setattr(
        "bedrock_server_manager.cli.setup.questionary", mock_questionary
    )

    monkeypatch.setattr(
        "bedrock_server_manager.cli.service.questionary", mock_questionary
    )

    bcm_config.set_custom_data_dir(None)
    result = runner.invoke(setup, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Setup complete!" in result.output
    assert "Using the default SQLite database" in result.output

    persisted = json.loads(
        (Path(bcm_config.get_config_dir()) / "bedrock_server_manager.json").read_text()
    )
    assert persisted["data_dir"] == str(tmp_path / "configured_data")
    assert "db_url" not in persisted
    assert app_context.settings.get("web.host") == "0.0.0.0"
    assert app_context.settings.get("web.port") == 12345
    unit = systemd.path().read_text()
    assert f"WorkingDirectory={app_context.data_dir}" in unit
    assert "web start --mode direct" in unit
    assert systemd.enabled
    assert any("enable" in command for command in systemd.commands)


def test_setup_advanced_db(runner, app_context, monkeypatch, tmp_path):
    """Test setup workflow successfully configures advanced database values and overrides configs."""
    mock_questionary = MagicMock()
    # 1. data_dir
    # 2. advance_db confirm (True)
    # 3. DB Url
    # 4. web_host
    # 5. web_port
    # 6. service config confirm (False)
    mock_questionary.text().ask.side_effect = [
        str(tmp_path / "configured_data"),
        f"sqlite:///{tmp_path / 'configured.db'}",
        "1.2.3.4",
        "80",
    ]
    mock_questionary.confirm().ask.side_effect = [True, False]
    monkeypatch.setattr(
        "bedrock_server_manager.cli.setup.questionary", mock_questionary
    )

    bcm_config.set_custom_data_dir(None)
    result = runner.invoke(setup, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert (
        bcm_config.load_config()["db_url"] == f"sqlite:///{tmp_path / 'configured.db'}"
    )
    assert "Database URL set to:" in result.output
    assert "Skipping service configuration." in result.output

    assert app_context.settings.get("web.host") == "1.2.3.4"
    assert app_context.settings.get("web.port") == 80
