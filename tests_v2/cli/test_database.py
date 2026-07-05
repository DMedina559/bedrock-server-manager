import json
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.database import database


@pytest.fixture
def runner():
    return CliRunner()


def test_database_upgrade(runner, app_context, monkeypatch):
    """Test database upgrade CLI command queries alembic successfully."""
    mock_command = MagicMock()
    monkeypatch.setattr("bedrock_server_manager.cli.database.command", mock_command)

    # Needs to pretend not to have alembic_version for baseline stamping
    mock_inspector = MagicMock()
    mock_inspector.has_table.return_value = False

    def mock_inspect(*args, **kwargs):
        return mock_inspector

    monkeypatch.setattr("bedrock_server_manager.cli.database.inspect", mock_inspect)

    result = runner.invoke(database, ["upgrade"], obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Running database upgrade" in result.output
    mock_command.upgrade.assert_called_once()


def test_database_downgrade(runner, app_context, monkeypatch):
    """Test database downgrade CLI command executes and prompts for downgrade correctly."""
    mock_command = MagicMock()
    monkeypatch.setattr("bedrock_server_manager.cli.database.command", mock_command)

    # Provide 'y' to the confirm prompt
    result = runner.invoke(
        database,
        ["downgrade", "-r", "-1"],
        input="y\n",
        obj={"app_context": app_context},
    )
    assert result.exit_code == 0
    assert "Running database downgrade" in result.output
    mock_command.downgrade.assert_called_once()


def test_database_downgrade_abort(runner, app_context):
    """Test database downgrade CLI command gracefully aborts upon confirmation rejection."""
    result = runner.invoke(
        database,
        ["downgrade", "-r", "-1"],
        input="n\n",
        obj={"app_context": app_context},
    )
    assert result.exit_code == 1  # aborted
    assert "Aborted!" in result.output


def test_database_backup(runner, app_context, tmp_path, monkeypatch):
    """Test database backup CLI command saves file correctly."""
    monkeypatch.setattr(
        "bedrock_server_manager.cli.database.backup_database", MagicMock()
    )

    out_file = tmp_path / "backup.json"
    result = runner.invoke(
        database, ["backup", "-o", str(out_file)], obj={"app_context": app_context}
    )

    assert result.exit_code == 0
    assert "Database data backup successful" in result.output


def test_database_backup_default_path(runner, app_context, tmp_path, monkeypatch):
    """Test database backup CLI command uses default settings correctly when not specifying -o."""
    app_context.settings.set("paths.backups", str(tmp_path))
    monkeypatch.setattr(
        "bedrock_server_manager.cli.database.backup_database", MagicMock()
    )

    result = runner.invoke(database, ["backup"], obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Database data backup successful" in result.output
    assert str(tmp_path) in result.output


def test_database_restore_success(runner, app_context, tmp_path, monkeypatch):
    """Test database restore CLI command restores data successfully."""
    in_file = tmp_path / "backup.json"
    with open(in_file, "w") as f:
        json.dump({"_metadata": {"alembic_version": "some_rev"}}, f)

    mock_questionary = MagicMock()
    mock_questionary.confirm().ask.return_value = True
    monkeypatch.setattr(
        "bedrock_server_manager.cli.database.questionary", mock_questionary
    )
    monkeypatch.setattr(
        "bedrock_server_manager.cli.database.get_current_db_revision",
        lambda x: "some_rev",
    )
    monkeypatch.setattr(
        "bedrock_server_manager.cli.database.restore_database", MagicMock()
    )

    result = runner.invoke(
        database, ["restore", "-i", str(in_file)], obj={"app_context": app_context}
    )
    assert result.exit_code == 0
    assert "Database data restore successful" in result.output


def test_database_restore_abort_prompt(runner, app_context, tmp_path, monkeypatch):
    """Test database restore CLI command correctly aborts on prompt denial."""
    in_file = tmp_path / "backup.json"
    in_file.touch()

    mock_questionary = MagicMock()
    mock_questionary.confirm().ask.return_value = False  # User says NO
    monkeypatch.setattr(
        "bedrock_server_manager.cli.database.questionary", mock_questionary
    )

    result = runner.invoke(
        database, ["restore", "-i", str(in_file)], obj={"app_context": app_context}
    )
    assert result.exit_code == 1  # aborted
    assert "Operation cancelled" in result.output


def test_database_restore_version_mismatch(runner, app_context, tmp_path, monkeypatch):
    """Test database restore CLI command properly detects version mismatch."""
    in_file = tmp_path / "backup.json"
    with open(in_file, "w") as f:
        json.dump({"_metadata": {"alembic_version": "old_rev"}}, f)

    mock_questionary = MagicMock()
    # First confirm is to proceed with wipe, second is to proceed despite version mismatch
    mock_questionary.confirm().ask.side_effect = [True, False]
    monkeypatch.setattr(
        "bedrock_server_manager.cli.database.questionary", mock_questionary
    )
    monkeypatch.setattr(
        "bedrock_server_manager.cli.database.get_current_db_revision",
        lambda x: "new_rev",
    )

    result = runner.invoke(
        database, ["restore", "-i", str(in_file)], obj={"app_context": app_context}
    )
    assert result.exit_code == 1  # aborted
    assert "Database version mismatch" in result.output
    assert "Operation cancelled" in result.output
