import json
import os
from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.config import bcm_config


@pytest.fixture
def clean_env(monkeypatch):
    """Ensure environment variables don't bleed into bcm_config tests."""
    monkeypatch.delenv("BSM_DATA_DIR", raising=False)
    monkeypatch.delenv("BSM_DB_URL", raising=False)
    monkeypatch.delenv("BSM_CONFIG_DIR", raising=False)
    monkeypatch.delenv("BSM_LOG_LEVEL", raising=False)

    # Also clean up the module-level globals so they don't bleed across tests
    bcm_config.set_custom_config_dir(None)
    bcm_config.set_custom_data_dir(None)
    bcm_config.set_custom_db_url(None)
    bcm_config.set_custom_log_level(None)
    yield
    bcm_config.set_custom_config_dir(None)
    bcm_config.set_custom_data_dir(None)
    bcm_config.set_custom_db_url(None)
    bcm_config.set_custom_log_level(None)


def test_get_config_dir_cli_override(clean_env):
    """Test get_config_dir returns the CLI override if set."""
    bcm_config.set_custom_config_dir("/cli/config")
    assert bcm_config.get_config_dir() == "/cli/config"


def test_get_config_dir_env_var(clean_env, monkeypatch):
    """Test get_config_dir returns the env var if set."""
    monkeypatch.setenv("BSM_CONFIG_DIR", "/env/config")
    assert bcm_config.get_config_dir() == "/env/config"


def test_get_config_dir_default(clean_env, monkeypatch):
    """Test get_config_dir returns the user config dir default."""
    mock_user_config_dir = MagicMock(return_value="/default/config")
    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.user_config_dir", mock_user_config_dir
    )
    assert bcm_config.get_config_dir() == "/default/config"


def test_get_config_path(isolated_bcm_config):
    """Test get_config_path returns the full path to json file."""
    expected = os.path.join(str(isolated_bcm_config), "bedrock_server_manager.json")
    assert bcm_config.get_config_path() == expected


def test_load_config_priority(clean_env, monkeypatch, tmp_path):
    """Test priority order: 1. CLI Override, 2. Env Var, 3. Config File, 4. Default"""
    mock_config_dir = tmp_path / "mock_config"
    mock_config_dir.mkdir()

    bcm_config.set_custom_config_dir(str(mock_config_dir))

    # The tests use "bedrock_server_manager.json" matching the original file name string
    config_file = mock_config_dir / "bedrock_server_manager.json"
    with open(config_file, "w") as f:
        json.dump(
            {
                "data_dir": "/file/data",
                "db_url": "sqlite:////file/db.sqlite",
                "logging_level": "WARNING",
            },
            f,
        )

    # Test Config File Only
    config = bcm_config.load_config()
    assert config["data_dir"] == "/file/data"
    assert config["db_url"] == "sqlite:////file/db.sqlite"
    assert config["logging_level"] == "WARNING"

    # Test Env Var overrides Config File
    monkeypatch.setenv("BSM_DATA_DIR", "/env/data")
    monkeypatch.setenv("BSM_DB_URL", "sqlite:////env/db.sqlite")
    monkeypatch.setenv("BSM_LOG_LEVEL", "error")

    config = bcm_config.load_config()
    assert config["data_dir"] == "/env/data"
    assert config["db_url"] == "sqlite:////env/db.sqlite"
    assert config["logging_level"] == "ERROR"

    # Test CLI Override overrides Env Var
    bcm_config.set_custom_data_dir("/cli/data")
    bcm_config.set_custom_log_level("debug")
    bcm_config.set_custom_db_url("sqlite:////cli/db.sqlite")

    config = bcm_config.load_config()
    assert config["data_dir"] == "/cli/data"
    assert config["db_url"] == "sqlite:////cli/db.sqlite"
    assert config["logging_level"] == "DEBUG"


def test_load_config_defaults(clean_env, monkeypatch, tmp_path):
    """Test load_config creates defaults if file is missing and env vars are not set."""
    mock_config_dir = tmp_path / "mock_config"
    mock_config_dir.mkdir()

    bcm_config.set_custom_config_dir(str(mock_config_dir))

    config = bcm_config.load_config()

    assert "data_dir" in config
    assert "db_url" in config
    assert "logging_level" in config
    assert config["data_dir"] == os.path.join(str(mock_config_dir), "data")
    assert config["logging_level"] == "INFO"
    assert os.path.exists(
        os.path.join(str(mock_config_dir), "bedrock_server_manager.json")
    )


def test_load_config_invalid_json(clean_env, tmp_path, caplog):
    """Test load_config handles invalid JSON gracefully."""
    mock_config_dir = tmp_path / "mock_config"
    mock_config_dir.mkdir()

    bcm_config.set_custom_config_dir(str(mock_config_dir))

    config_file = mock_config_dir / "bedrock_server_manager.json"
    with open(config_file, "w") as f:
        f.write("{invalid json}")

    config = bcm_config.load_config()

    # It should fall back to generating defaults
    assert "data_dir" in config
    assert "Failed to load configuration file" in caplog.text


def test_set_and_get_config_value(isolated_bcm_config):
    """Test set_config_value and get_config_value for nested and top-level keys."""
    # Top level
    bcm_config.set_config_value("test_key", "test_value")
    assert bcm_config.get_config_value("test_key") == "test_value"

    # Nested key
    bcm_config.set_config_value("nested", {"key": "val"})
    assert bcm_config.get_config_value("nested.key") == "val"

    # Default value
    assert bcm_config.get_config_value("nonexistent", "default") == "default"
    assert bcm_config.get_config_value("nested.nonexistent", "default") == "default"


def test_save_config_creates_dir(clean_env, tmp_path):
    """Test save_config successfully creates directory if it doesn't exist."""
    new_dir = tmp_path / "new_dir"

    bcm_config.set_custom_config_dir(str(new_dir))
    bcm_config.save_config({"key": "value"})

    assert new_dir.exists()
    assert (new_dir / "bedrock_server_manager.json").exists()


def test_save_config_error(isolated_bcm_config, monkeypatch, caplog):
    """Test save_config logs an error on failure."""

    def mock_makedirs(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr("os.makedirs", mock_makedirs)
    bcm_config.save_config({"key": "value"})

    assert "Failed to save configuration file" in caplog.text


def test_needs_setup(app_context):
    """Test needs_setup correctly identifies if admin users exist."""
    from bedrock_server_manager.db.models import User

    app_context._needs_setup = None  # Reset cache

    with app_context.db.session_manager() as db:
        db.query(User).delete()
        db.commit()

    assert app_context.needs_setup is True

    app_context._needs_setup = None  # Reset cache

    with app_context.db.session_manager() as db:
        db.add(User(username="test", hashed_password="pw", role="admin"))
        db.commit()

    assert app_context.needs_setup is False
