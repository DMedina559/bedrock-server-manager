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


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def settings(db_session, monkeypatch, tmp_path):
    # Setup for the settings instance
    test_data_dir = tmp_path / "test_app_data"
    test_data_dir.mkdir()
    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(test_data_dir))

    # Point the settings to use the test database
    monkeypatch.setattr(
        "bedrock_server_manager.config.settings.SessionLocal", lambda: db_session
    )

    # Invalidate any existing singleton instance
    Settings._instance = None

    settings_instance = Settings()

    yield settings_instance

    # Teardown
    Settings._instance = None


def test_initialization_with_defaults(settings):
    """Test that settings are initialized with default values."""
    assert settings.get("config_version") == CONFIG_SCHEMA_VERSION
    assert settings.get("retention.backups") == 3
    assert settings.get("web.port") == 11325


def test_setting_and_getting_values(settings):
    """Test that setting a value is persisted and retrievable."""
    settings.set("web.port", 8000)
    assert settings.get("web.port") == 8000

    settings.set("retention.logs", 10)
    assert settings.get("retention.logs") == 10


def test_nested_setting_and_getting(settings):
    """Test that nested values can be set and retrieved."""
    settings.set("paths.servers", "/new/server/path")
    assert settings.get("paths.servers") == "/new/server/path"

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


def test_singleton_behavior(settings):
    """Test that the Settings class behaves as a singleton."""
    new_settings_instance = Settings()
    assert new_settings_instance is settings

    settings.set("custom.test_singleton", True)
    assert new_settings_instance.get("custom.test_singleton") is True


def test_get_with_default_value(settings):
    """Test that the get method returns the default value if the key does not exist."""
    assert settings.get("non_existent_key", "default_value") == "default_value"


def test_set_with_new_key(settings):
    """Test that the set method can create a new key."""
    settings.set("new_key", "new_value")
    assert settings.get("new_key") == "new_value"


def test_determine_app_data_dir(monkeypatch, tmp_path):
    """Test that the _determine_app_data_dir method returns the correct directory."""
    # Test with environment variable
    test_data_dir = tmp_path / "test_app_data"
    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(test_data_dir))
    settings = Settings()
    assert settings._determine_app_data_dir() == str(test_data_dir)
    Settings._instance = None

    # Test without environment variable
    monkeypatch.delenv(f"{env_name}_DATA_DIR")
    settings = Settings()
    assert settings._determine_app_data_dir() == os.path.join(
        os.path.expanduser("~"), f"{package_name}"
    )
    Settings._instance = None


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


def test_write_config_error(settings, monkeypatch):
    """Test that a ConfigurationError is raised if the config cannot be written."""

    def mock_commit():
        raise Exception("Test Exception")

    monkeypatch.setattr(settings.db, "commit", mock_commit)
    with pytest.raises(Exception, match="Test Exception"):
        settings._write_config()


def test_deep_merge():
    """Test the deep_merge function."""
    source = {"a": 1, "b": {"c": 2, "d": 3}}
    destination = {"b": {"c": 4, "e": 5}, "f": 6}

    deep_merge(source, destination)

    assert destination == {"a": 1, "b": {"c": 2, "d": 3, "e": 5}, "f": 6}
