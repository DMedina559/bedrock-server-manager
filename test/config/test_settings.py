import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bedrock_server_manager.config.const import package_name, env_name
from bedrock_server_manager.config.settings import (
    Settings,
    CONFIG_SCHEMA_VERSION,
    deep_merge,
)
from bedrock_server_manager.db.database import Base
from bedrock_server_manager.db.models import Setting


from unittest.mock import MagicMock


@pytest.fixture
def settings(app_context):
    return app_context.settings


def test_initialization_with_defaults(settings):
    """Test that settings are initialized with default values."""
    assert settings.get("config_version") == CONFIG_SCHEMA_VERSION
    assert settings.get("retention.backups") == 3
    assert settings.get("web.port") == 11325


def test_setting_and_getting_values(settings, db_session):
    """Test that setting a value is persisted and retrievable."""
    settings.set("web.port", 8000)
    assert settings.get("web.port") == 8000

    # Check the database directly
    setting_in_db = db_session.query(Setting).filter_by(key="web").one()
    assert setting_in_db.value["port"] == 8000

    settings.set("retention.logs", 10)
    assert settings.get("retention.logs") == 10

    # Check the database directly
    setting_in_db = db_session.query(Setting).filter_by(key="retention").one()
    assert setting_in_db.value["logs"] == 10


def test_nested_setting_and_getting(settings, db_session, tmp_path):
    """Test that nested values can be set and retrieved."""
    new_path = tmp_path / "new_server_path"
    settings.set("paths.servers", str(new_path))
    assert settings.get("paths.servers") == str(new_path)

    # Check the database directly
    setting_in_db = db_session.query(Setting).filter_by(key="paths").one()
    assert setting_in_db.value["servers"] == str(new_path)

    # Ensure other nested values are not affected
    assert settings.get("paths.backups") is not None


def test_reload_settings(settings, db_session):
    """Test that settings can be reloaded from the database."""
    settings.set("web.port", 12345)

    # Manually change the value in the database
    setting_in_db = db_session.query(Setting).filter_by(key="web").first()

    # The value is stored as a dictionary
    setting_in_db.value = {"port": 54321}
    db_session.commit()

    # Re-fetch to confirm the change in the DB
    refreshed_setting = db_session.query(Setting).filter_by(key="web").first()
    assert refreshed_setting.value["port"] == 54321

    settings.reload()

    assert settings.get("web.port") == 54321


def test_get_with_default_value(settings):
    """Test that the get method returns the default value if the key does not exist."""
    assert settings.get("non_existent_key", "default_value") == "default_value"


def test_set_with_new_key(settings):
    """Test that the set method can create a new key."""
    settings.set("new_key", "new_value")
    assert settings.get("new_key") == "new_value"


from unittest.mock import patch


from unittest.mock import patch


def test_determine_app_data_dir_uses_config(settings, monkeypatch, tmp_path):
    """Test that _determine_app_data_dir uses the data_dir from bcm_config."""
    with patch(
        "bedrock_server_manager.config.settings.bcm_config.load_config"
    ) as mock_load_config:
        config_dir = str(tmp_path / "config_dir")
        mock_load_config.return_value = {"data_dir": config_dir}
        assert settings._determine_app_data_dir() == config_dir


def test_determine_app_config_dir(settings):
    """Test that the _determine_app_config_dir method returns the correct directory."""
    assert settings._determine_app_config_dir() == os.path.join(
        settings.app_data_dir, ".config"
    )


def test_ensure_dirs_exist(settings):
    """Test that the _ensure_dirs_exist method creates the necessary directories."""
    settings._ensure_dirs_exist()
    for path in settings.get("paths").values():
        assert os.path.exists(path)


def test_write_config_error(settings, db_session, monkeypatch):
    """Test that a ConfigurationError is raised if the config cannot be written."""

    def mock_commit():
        raise Exception("Test Exception")

    monkeypatch.setattr(db_session, "commit", mock_commit)
    with pytest.raises(Exception, match="Test Exception"):
        settings._write_config(db_session)


def test_deep_merge():
    """Test the deep_merge function."""
    source = {"a": 1, "b": {"c": 2, "d": 3}}
    destination = {"b": {"c": 4, "e": 5}, "f": 6}

    deep_merge(source, destination)

    assert destination == {"a": 1, "b": {"c": 2, "d": 3, "e": 5}, "f": 6}
