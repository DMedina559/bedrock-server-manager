import os

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    """Ensure environment variables don't bleed into bcm_config tests."""
    monkeypatch.delenv("BSM_DATA_DIR", raising=False)
    monkeypatch.delenv("BSM_DB_URL", raising=False)


def test_get_config_dir(isolated_bcm_config):
    """Test get_config_dir returns the mocked directory."""
    from bedrock_server_manager.config import bcm_config

    expected = str(isolated_bcm_config)
    assert bcm_config.get_config_dir() == expected


def test_get_config_path(isolated_bcm_config):
    """Test get_config_path returns the full path to json file."""
    # Since isolated_bcm_config mocks user_config_dir,
    # get_config_dir will return the string path.
    from bedrock_server_manager.config import bcm_config

    expected = os.path.join(str(isolated_bcm_config), "bedrock_server_manager.json")
    assert bcm_config.get_config_path() == expected


def test_load_config_defaults(clean_env, monkeypatch, tmp_path):
    """Test load_config creates defaults if file is missing and env vars are not set."""
    mock_config_dir = tmp_path / "mock_config"
    mock_config_dir.mkdir()

    def my_mock(appname=None, *args, **kwargs):
        return (
            os.path.join(str(mock_config_dir), appname)
            if appname
            else str(mock_config_dir)
        )

    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.user_config_dir", my_mock
    )

    import importlib

    from bedrock_server_manager.config import bcm_config

    importlib.reload(bcm_config)
    monkeypatch.setattr(bcm_config, "user_config_dir", my_mock)

    config = bcm_config.load_config()

    assert "data_dir" in config
    assert "db_url" in config
    assert config["data_dir"].startswith(os.path.expanduser("~"))
    assert os.path.exists(
        os.path.join(
            str(mock_config_dir), bcm_config.package_name, "bedrock_server_manager.json"
        )
    )


def test_load_config_from_env_vars(monkeypatch, tmp_path):
    """Test load_config respects environment variables over defaults."""
    mock_config_dir = tmp_path / "mock_config"
    mock_config_dir.mkdir()

    def my_mock(appname=None, *args, **kwargs):
        return (
            os.path.join(str(mock_config_dir), appname)
            if appname
            else str(mock_config_dir)
        )

    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.user_config_dir", my_mock
    )

    monkeypatch.setenv("BSM_DATA_DIR", "/custom/data")
    monkeypatch.setenv("BSM_DB_URL", "sqlite:////custom/db.sqlite")

    import importlib

    from bedrock_server_manager.config import bcm_config

    importlib.reload(bcm_config)
    monkeypatch.setattr(bcm_config, "user_config_dir", my_mock)

    config = bcm_config.load_config()

    assert config["data_dir"] == "/custom/data"
    assert config["db_url"] == "sqlite:////custom/db.sqlite"


def test_load_config_invalid_json(tmp_path, monkeypatch, caplog):
    """Test load_config handles invalid JSON gracefully."""
    mock_config_dir = tmp_path / "mock_config"
    mock_config_dir.mkdir()

    def my_mock(appname=None, *args, **kwargs):
        return (
            os.path.join(str(mock_config_dir), appname)
            if appname
            else str(mock_config_dir)
        )

    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.user_config_dir", my_mock
    )

    import importlib

    from bedrock_server_manager.config import bcm_config

    importlib.reload(bcm_config)
    monkeypatch.setattr(bcm_config, "user_config_dir", my_mock)

    # Create the file bcm_config expects
    config_dir_path = os.path.join(str(mock_config_dir), bcm_config.package_name)
    os.makedirs(config_dir_path, exist_ok=True)
    config_file = os.path.join(config_dir_path, "bedrock_server_manager.json")

    with open(config_file, "w") as f:
        f.write("{invalid json}")

    config = bcm_config.load_config()

    # It should fall back to generating defaults
    assert "data_dir" in config
    assert "Failed to load configuration file" in caplog.text


def test_set_and_get_config_value(isolated_bcm_config):
    """Test set_config_value and get_config_value for nested and top-level keys."""
    from bedrock_server_manager.config import bcm_config

    # Top level
    bcm_config.set_config_value("test_key", "test_value")
    assert bcm_config.get_config_value("test_key") == "test_value"

    # Nested key
    bcm_config.set_config_value("nested", {"key": "val"})
    assert bcm_config.get_config_value("nested.key") == "val"

    # Default value
    assert bcm_config.get_config_value("nonexistent", "default") == "default"
    assert bcm_config.get_config_value("nested.nonexistent", "default") == "default"


def test_save_config_creates_dir(tmp_path, monkeypatch):
    """Test save_config successfully creates directory if it doesn't exist."""
    new_dir = tmp_path / "new_dir"

    def my_mock(appname=None, *args, **kwargs):
        return os.path.join(str(new_dir), appname) if appname else str(new_dir)

    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.user_config_dir", my_mock
    )

    import importlib

    from bedrock_server_manager.config import bcm_config

    importlib.reload(bcm_config)
    monkeypatch.setattr(bcm_config, "user_config_dir", my_mock)

    bcm_config.save_config({"key": "value"})

    assert new_dir.exists()
    assert (new_dir / bcm_config.package_name / "bedrock_server_manager.json").exists()


def test_save_config_error(isolated_bcm_config, monkeypatch, caplog):
    """Test save_config logs an error on failure."""
    from bedrock_server_manager.config import bcm_config

    def mock_makedirs(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr("os.makedirs", mock_makedirs)

    bcm_config.save_config({"key": "value"})

    assert "Failed to save configuration file" in caplog.text


def test_needs_setup(app_context):
    """Test needs_setup correctly identifies if users exist."""
    from bedrock_server_manager.config import bcm_config
    from bedrock_server_manager.db.models import User

    with app_context.db.session_manager() as db:
        db.query(User).delete()
        db.commit()

    assert bcm_config.needs_setup(app_context) is True

    with app_context.db.session_manager() as db:
        db.add(User(username="test", hashed_password="pw"))
        db.commit()

    assert bcm_config.needs_setup(app_context) is False
