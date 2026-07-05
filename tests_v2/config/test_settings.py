from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.db.models import Setting
from bedrock_server_manager.error import ConfigurationError


def test_settings_initialization(db):
    """Test Settings initializes properties correctly without loading."""
    settings = Settings(db=db)
    assert settings.db == db
    assert settings._settings == {}


def test_settings_load_populates_defaults(db):
    """Test loading on an empty database populates default settings."""
    settings = Settings(db=db)
    settings.load()

    # Check that settings were populated from default_config
    assert "web" in settings._settings
    assert "port" in settings._settings["web"]

    # Verify they were saved to the DB
    with db.session_manager() as session:
        count = session.query(Setting).count()
        assert count > 0


def test_settings_load_merges_existing_db(db):
    """Test loading merges DB user config over defaults."""
    # Pre-populate DB with a custom setting that overrides a default
    with db.session_manager() as session:
        session.add(
            Setting(
                key="web",
                value={"port": 9999, "host": "127.0.0.1", "token_expires_weeks": 4},
            )
        )
        session.add(Setting(key="custom", value={"my_setting": "val"}))
        session.commit()

    settings = Settings(db=db)
    settings.load()

    assert settings.get("web.port") == 9999
    assert settings.get("custom.my_setting") == "val"

    # Check that other defaults still exist
    assert settings.get("retention.backups") is not None


def test_settings_get(settings):
    """Test getting deeply nested keys and defaults."""
    assert settings.get("paths.servers") is not None
    assert settings.get("web.port") == 11325
    assert settings.get("does.not.exist", "fallback") == "fallback"
    assert settings.get("web.invalid", "fallback") == "fallback"


def test_settings_set(settings, db):
    """Test setting deeply nested keys."""
    # Test setting existing key
    settings.set("web.port", 8080)
    assert settings.get("web.port") == 8080

    # Test setting new nested key
    settings.set("custom.plugin.enabled", True)
    assert settings.get("custom.plugin.enabled") is True

    # Verify written to DB
    with db.session_manager() as session:
        custom_setting = session.query(Setting).filter_by(key="custom").first()
        assert custom_setting.value["plugin"]["enabled"] is True


def test_settings_set_no_change_skips_write(settings, monkeypatch):
    """Test setting the same value skips database write."""
    mock_write = MagicMock()
    monkeypatch.setattr(settings, "_write_config", mock_write)

    current_val = settings.get("web.port")
    settings.set("web.port", current_val)

    mock_write.assert_not_called()


def test_settings_set_conflict_raises_error(settings):
    """Test setting a key where a path conflict exists raises ConfigurationError."""
    # We must try to set a sub-key on a path that is already a primitive value, not a dict.
    # web.port is an int, so setting web.port.sub should throw a ConfigurationError.

    with pytest.raises(ConfigurationError, match="Cannot set key"):
        settings.set("web.port.sub.another", "value")


def test_settings_reload(settings, db):
    """Test reload pulls fresh changes from the database."""
    # Modify db directly
    with db.session_manager() as session:
        setting = session.query(Setting).filter_by(key="web").first()
        if not setting:
            setting = Setting(key="web", value={"port": 11325})
            session.add(setting)

        # we have to replace the whole dict in sqlalchemy JSON columns for it to register update sometimes,
        # or use flag_modified. The safest way is to reassign.
        new_val = dict(setting.value) if setting.value else {}
        new_val["port"] = 5555
        setting.value = new_val
        session.commit()

    assert settings.get("web.port") == 11325  # Before reload
    settings.reload()
    assert settings.get("web.port") == 5555  # After reload


def test_settings_ensure_dirs_exist(settings, tmp_path):
    """Test _ensure_dirs_exist creates critical directories."""
    # Change a path to a new location
    new_dir = tmp_path / "new_servers_dir"
    settings.set("paths.servers", str(new_dir))

    assert not new_dir.exists()
    settings._ensure_dirs_exist()
    assert new_dir.exists()


def test_settings_ensure_dirs_raises_error_on_failure(settings, monkeypatch):
    """Test _ensure_dirs_exist raises ConfigurationError on OSError."""

    def mock_makedirs(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr("os.makedirs", mock_makedirs)

    with pytest.raises(ConfigurationError, match="Could not create critical directory"):
        settings._ensure_dirs_exist()


def test_settings_properties(settings):
    """Test property getters like config_dir and app_data_dir."""
    assert settings.config_dir is not None
    assert settings.app_data_dir is not None
    assert isinstance(settings.version, str)
