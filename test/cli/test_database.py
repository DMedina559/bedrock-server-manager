import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

from bedrock_server_manager.cli.database import upgrade
from bedrock_server_manager.db.models import User


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_app_context(mocker):
    mock_db_session = MagicMock()
    mock_app_context = MagicMock()
    mock_app_context.db.session_manager.return_value.__enter__.return_value = (
        mock_db_session
    )
    mock_app_context.settings.get.return_value = "/fake/backups"
    # This is the key change to fix the unit tests
    mock_app_context.db.get_database_url.return_value = "sqlite:////fake/db.sqlite3"
    return mock_app_context, mock_db_session


from unittest.mock import call


def test_upgrade_sqlite_backup_success(runner, mock_app_context, mocker):
    mock_context, _ = mock_app_context
    db_url = mock_context.db.get_database_url()
    mocker.patch("bedrock_server_manager.cli.database.shutil.copy")
    mocker.patch("bedrock_server_manager.cli.database.command.upgrade")
    mock_config_instance = MagicMock()
    mocker.patch(
        "bedrock_server_manager.cli.database.Config", return_value=mock_config_instance
    )

    result = runner.invoke(upgrade, [], obj={"app_context": mock_context})

    assert result.exit_code == 0
    expected_calls = [
        call("skip_logging_config", "true"),
        call("sqlalchemy.url", db_url),
    ]
    mock_config_instance.set_main_option.assert_has_calls(
        expected_calls, any_order=True
    )
    assert "Database backed up to" in result.output
    assert "Database upgrade complete." in result.output


def test_upgrade_non_sqlite_warning(runner, mock_app_context, mocker):
    mock_context, _ = mock_app_context
    db_url = "postgresql://user:pass@host/db"
    mock_context.db.get_database_url.return_value = db_url
    mocker.patch("bedrock_server_manager.cli.database.command.upgrade")
    mock_config_instance = MagicMock()
    mocker.patch(
        "bedrock_server_manager.cli.database.Config", return_value=mock_config_instance
    )

    result = runner.invoke(upgrade, [], input="y\n", obj={"app_context": mock_context})

    assert result.exit_code == 0
    expected_calls = [
        call("skip_logging_config", "true"),
        call("sqlalchemy.url", db_url),
    ]
    mock_config_instance.set_main_option.assert_has_calls(
        expected_calls, any_order=True
    )
    assert "Your database is not SQLite" in result.output


def test_upgrade_admin_user_exists(runner, mock_app_context, mocker):
    mock_context, mock_session = mock_app_context
    db_url = mock_context.db.get_database_url()
    mock_session.query.return_value.filter.return_value.first.return_value = User(
        role="admin"
    )
    mocker.patch("bedrock_server_manager.cli.database.shutil.copy")
    mocker.patch("bedrock_server_manager.cli.database.command.upgrade")
    mock_config_instance = MagicMock()
    mocker.patch(
        "bedrock_server_manager.cli.database.Config", return_value=mock_config_instance
    )

    result = runner.invoke(upgrade, [], obj={"app_context": mock_context})

    assert result.exit_code == 0
    expected_calls = [
        call("skip_logging_config", "true"),
        call("sqlalchemy.url", db_url),
    ]
    mock_config_instance.set_main_option.assert_has_calls(
        expected_calls, any_order=True
    )
    assert "Warning: No admin user found" not in result.output


def test_upgrade_no_admin_user(runner, mock_app_context, mocker):
    mock_context, mock_session = mock_app_context
    db_url = mock_context.db.get_database_url()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mocker.patch("bedrock_server_manager.cli.database.shutil.copy")
    mocker.patch("bedrock_server_manager.cli.database.command.upgrade")
    mock_config_instance = MagicMock()
    mocker.patch(
        "bedrock_server_manager.cli.database.Config", return_value=mock_config_instance
    )

    result = runner.invoke(upgrade, [], obj={"app_context": mock_context})

    assert result.exit_code == 0
    expected_calls = [
        call("skip_logging_config", "true"),
        call("sqlalchemy.url", db_url),
    ]
    mock_config_instance.set_main_option.assert_has_calls(
        expected_calls, any_order=True
    )
    assert "Warning: No admin user found" in result.output


def test_upgrade_unmanaged_database_stamps(runner, mock_app_context, mocker):
    mock_context, _ = mock_app_context
    db_url = mock_context.db.get_database_url()
    mock_inspector = MagicMock()
    mock_inspector.has_table.side_effect = lambda table_name: table_name == "users"
    mocker.patch(
        "bedrock_server_manager.cli.database.inspect", return_value=mock_inspector
    )
    mocker.patch("bedrock_server_manager.cli.database.shutil.copy")
    mock_stamp = mocker.patch("bedrock_server_manager.cli.database.command.stamp")
    mock_upgrade = mocker.patch("bedrock_server_manager.cli.database.command.upgrade")
    mock_config_instance = MagicMock()
    mocker.patch(
        "bedrock_server_manager.cli.database.Config", return_value=mock_config_instance
    )

    result = runner.invoke(upgrade, [], obj={"app_context": mock_context})

    assert result.exit_code == 0
    expected_calls = [
        call("skip_logging_config", "true"),
        call("sqlalchemy.url", db_url),
    ]
    mock_config_instance.set_main_option.assert_has_calls(
        expected_calls, any_order=True
    )
    assert "Unmanaged database detected" in result.output
    mock_stamp.assert_called_once_with(mocker.ANY, "head")
    mock_upgrade.assert_called_once()


def test_upgrade_integration_unmanaged_db(runner, app_context):
    """
    Integration test to verify that the upgrade command correctly stamps
    an unmanaged database (one with tables but no alembic_version table).
    """
    from sqlalchemy import inspect

    # The app_context fixture creates an unmanaged database for us.
    # We just need to run the command.
    result = runner.invoke(upgrade, [], obj={"app_context": app_context})

    # 1. Check the output and exit code
    assert result.exit_code == 0, result.output
    assert "Unmanaged database detected" in result.output
    assert "Database stamped successfully" in result.output
    assert "Running database upgrade" in result.output
    assert "Database upgrade complete" in result.output

    # 2. Verify that the alembic_version table was created
    engine = app_context.db.engine
    inspector = inspect(engine)
    assert inspector.has_table("alembic_version")


def test_upgrade_e2e_unmanaged_db(tmp_path, monkeypatch):
    """
    A high-fidelity integration test that simulates running the CLI from scratch
    on an unmanaged database, ensuring the app's full startup sequence is tested.
    """
    import json
    from sqlalchemy import create_engine, inspect
    from bedrock_server_manager.db.models import Base
    from bedrock_server_manager.__main__ import create_cli_app
    from click.testing import CliRunner

    # 1. Setup Environment
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()

    db_path = data_dir / "test_e2e.db"
    db_url = f"sqlite:///{db_path}"

    # Create the main config file that the app will find
    app_config_file = config_dir / "bedrock_server_manager.json"
    with open(app_config_file, "w") as f:
        json.dump({"data_dir": str(data_dir), "db_url": db_url}, f)

    # Monkeypatch the config directory path finder
    monkeypatch.setattr(
        "appdirs.user_config_dir", lambda *args, **kwargs: str(config_dir)
    )

    # Reload the config module to ensure it uses the monkeypatched path
    from bedrock_server_manager.config import bcm_config
    import importlib

    importlib.reload(bcm_config)

    # 2. Create the unmanaged database
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    assert not inspect(engine).has_table("alembic_version")
    assert inspect(engine).has_table("users")

    # 3. Run the CLI command
    runner = CliRunner()
    cli_app = create_cli_app()
    result = runner.invoke(cli_app, ["database", "upgrade"], catch_exceptions=False)

    # 4. Assert the results
    assert result.exit_code == 0, result.output
    assert "Unmanaged database detected" in result.output
    assert "Database stamped successfully" in result.output
    assert "Running database upgrade" in result.output
    assert "Database upgrade complete" in result.output

    # Verify the table was created in the database file
    engine_after = create_engine(db_url)
    assert inspect(engine_after).has_table("alembic_version")


def test_upgrade_e2e_empty_alembic_table(tmp_path, monkeypatch):
    """
    Tests that the upgrade command works correctly when the alembic_version
    table exists but is empty (contains NULL).
    """
    import json
    from sqlalchemy import create_engine, inspect, text
    from bedrock_server_manager.db.models import Base
    from bedrock_server_manager.__main__ import create_cli_app
    from click.testing import CliRunner

    # 1. Setup Environment
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()
    db_path = data_dir / "test_e2e_empty.db"
    db_url = f"sqlite:///{db_path}"
    app_config_file = config_dir / "bedrock_server_manager.json"
    with open(app_config_file, "w") as f:
        json.dump({"data_dir": str(data_dir), "db_url": db_url}, f)
    monkeypatch.setattr(
        "appdirs.user_config_dir", lambda *args, **kwargs: str(config_dir)
    )

    # Reload the config module to ensure it uses the monkeypatched path
    from bedrock_server_manager.config import bcm_config
    import importlib

    importlib.reload(bcm_config)

    # 2. Create the database in the problematic state
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)  # Create all tables
    with engine.connect() as connection:
        # Manually create the alembic_version table
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.commit()

    assert inspect(engine).has_table("alembic_version")
    assert inspect(engine).has_table("users")

    # 3. Run the CLI command
    runner = CliRunner()
    cli_app = create_cli_app()
    result = runner.invoke(cli_app, ["database", "upgrade"], catch_exceptions=False)

    # 4. Assert the results
    assert result.exit_code == 0, result.output
    assert "stamping" in result.output.lower()

    # 5. Verify the table is now correctly stamped
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
        assert result is not None
