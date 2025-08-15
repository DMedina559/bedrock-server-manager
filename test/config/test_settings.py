# Test cases for bedrock_server_manager.config.settings
import pytest
import os
import json
import shutil
import logging  # Import logging
from pathlib import Path

# Assuming the module is in src/bedrock_server_manager/config/settings.py
# Adjust the import path if your project structure is different.
# This might require adding src to PYTHONPATH or using relative imports if tests are part of the package.
from bedrock_server_manager.config.settings import (
    Settings,
    deep_merge,
    CONFIG_SCHEMA_VERSION,
    NEW_CONFIG_FILE_NAME,
    OLD_CONFIG_FILE_NAME,
)
from bedrock_server_manager.config.const import package_name, env_name
from bedrock_server_manager.error import ConfigurationError


# Helper function to create a dummy config file
def create_dummy_config(config_path: Path, content: dict):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(content, f, indent=4)


# Helper function to read a config file
def read_json_file(file_path: Path) -> dict:
    with open(file_path, "r") as f:
        return json.load(f)


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory for config files."""
    # tmp_path is a built-in pytest fixture providing a Path object to a temporary directory
    return tmp_path


@pytest.fixture
def settings_instance(tmp_config_dir: Path, monkeypatch) -> Settings:
    """
    Creates a Settings instance using a temporary config directory.
    Temporarily overrides environment variables for BSM_DATA_DIR and cleans up.
    """
    # Define a temporary data directory within the test's tmp_path structure
    test_data_dir = tmp_config_dir / "test_app_data"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # Temporarily set the BSM_DATA_DIR environment variable using the correct env_name
    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(test_data_dir))

    # The Settings class constructor will use this env var to determine paths
    settings = Settings()

    # Ensure the settings object is using the correct temporary path
    # This is more of an assertion for the fixture's correctness
    assert settings.app_data_dir == str(test_data_dir)
    assert settings.config_dir == str(test_data_dir / ".config")
    assert settings.config_path == str(test_data_dir / ".config" / NEW_CONFIG_FILE_NAME)

    yield settings

    # Teardown: monkeypatch automatically undoes env var changes.
    # shutil.rmtree(test_data_dir) # tmp_path handles cleanup of its contents


def test_settings_initialization_default(
    settings_instance: Settings, tmp_config_dir: Path
):
    """Test Settings initialization with default values when no config file exists."""
    config_file = Path(settings_instance.config_path)

    assert config_file.exists()
    loaded_settings = read_json_file(config_file)

    assert loaded_settings["config_version"] == CONFIG_SCHEMA_VERSION
    assert loaded_settings["paths"]["servers"] == str(
        tmp_config_dir / "test_app_data" / "servers"
    )
    assert loaded_settings["retention"]["backups"] == 3
    # Check a few default values
    assert settings_instance.get("retention.backups") == 3
    assert settings_instance.get("web.port") == 11325
    assert settings_instance.get("non_existent.key") is None
    assert settings_instance.get("non_existent.key", "default_val") == "default_val"


def test_settings_load_existing_config(
    settings_instance: Settings, tmp_config_dir: Path
):
    """Test Settings loading from an existing v2 config file."""
    custom_config_content = {
        "config_version": CONFIG_SCHEMA_VERSION,
        "paths": {
            "servers": str(tmp_config_dir / "custom_server_path"),  # Use temp path
            "logs": str(tmp_config_dir / "custom_logs"),
        },
        "retention": {"backups": 10},
        "logging": {"cli_level": 10},  # Example: logging.DEBUG
        "custom": {"my_setting": "my_value"},
    }
    config_file = Path(settings_instance.config_path)
    create_dummy_config(config_file, custom_config_content)

    settings_instance.reload()  # Reload to pick up the created file

    assert settings_instance.get("paths.servers") == str(
        tmp_config_dir / "custom_server_path"
    )
    assert settings_instance.get("paths.logs") == str(tmp_config_dir / "custom_logs")
    assert settings_instance.get("paths.content") == str(
        Path(settings_instance.app_data_dir) / "content"
    )  # check default value is still there, relative to correct app_data_dir
    assert settings_instance.get("retention.backups") == 10
    assert settings_instance.get("logging.cli_level") == 10
    assert settings_instance.get("custom.my_setting") == "my_value"
    # Ensure directories mentioned in config are created
    assert Path(settings_instance.get("paths.logs")).exists()


def test_settings_set_and_save(settings_instance: Settings):
    """Test setting a value and saving it to the config file."""
    settings_instance.set("web.host", "0.0.0.0")
    settings_instance.set("retention.logs", 7)
    settings_instance.set("new_category.new_setting.nested", "nested_value")

    config_file = Path(settings_instance.config_path)
    loaded_settings = read_json_file(config_file)

    assert loaded_settings["web"]["host"] == "0.0.0.0"
    assert loaded_settings["retention"]["logs"] == 7
    assert loaded_settings["new_category"]["new_setting"]["nested"] == "nested_value"

    # Test that setting the same value doesn't rewrite (not easily testable without mocks for _write_config)
    # For now, just ensure the value remains correct
    settings_instance.set("web.host", "0.0.0.0")
    assert settings_instance.get("web.host") == "0.0.0.0"


def test_settings_migrate_old_filename(tmp_config_dir: Path, monkeypatch):
    """Test migration from old config filename to new config filename."""
    test_data_dir = tmp_config_dir / "test_app_data_migration"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    config_dir_path = test_data_dir / ".config"
    config_dir_path.mkdir(parents=True, exist_ok=True)

    old_config_file = config_dir_path / OLD_CONFIG_FILE_NAME
    new_config_file = config_dir_path / NEW_CONFIG_FILE_NAME

    # Create a dummy old config file (can be v1 or v2 content, filename is key)
    dummy_content = {"config_version": CONFIG_SCHEMA_VERSION, "web": {"port": 12345}}
    create_dummy_config(old_config_file, dummy_content)

    assert old_config_file.exists()
    assert not new_config_file.exists()

    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(test_data_dir))
    settings = Settings()  # Instantiation should trigger migration

    assert not old_config_file.exists()  # Old file should be renamed
    assert new_config_file.exists()
    assert settings.config_path == str(new_config_file)
    assert settings.get("web.port") == 12345


def test_settings_migrate_v1_to_v2(tmp_config_dir: Path, monkeypatch):
    """Test migration from v1 (flat) config to v2 (nested) config."""
    test_data_dir = tmp_config_dir / "test_app_data_v1_migration"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    config_dir_path = test_data_dir / ".config"
    config_dir_path.mkdir(parents=True, exist_ok=True)

    config_file = config_dir_path / NEW_CONFIG_FILE_NAME

    # Create a dummy v1 config file
    v1_servers_path = (
        test_data_dir / "v1_servers"
    )  # Use a path within the temp structure
    v1_content = {"BASE_DIR": str(v1_servers_path), "BACKUP_KEEP": 5, "WEB_PORT": 8000}
    create_dummy_config(config_file, v1_content)

    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(test_data_dir))
    settings = Settings()  # Instantiation should trigger migration

    backup_v1_file = Path(str(config_file) + ".v1.bak")
    assert backup_v1_file.exists()  # Old v1 file should be backed up

    assert settings.get("config_version") == CONFIG_SCHEMA_VERSION
    assert settings.get("paths.servers") == str(v1_servers_path)
    assert settings.get("retention.backups") == 5
    assert settings.get("web.port") == 8000
    # Check a default v2 value that wasn't in v1
    assert (
        settings.get("logging.cli_level")
        == settings.default_config["logging"]["cli_level"]
    )

    loaded_settings = read_json_file(config_file)
    assert loaded_settings["config_version"] == CONFIG_SCHEMA_VERSION
    assert loaded_settings["paths"]["servers"] == str(v1_servers_path)


def test_settings_ensure_dirs_created(settings_instance: Settings):
    """Test that critical directories are created."""
    assert Path(settings_instance.get("paths.servers")).exists()
    assert Path(settings_instance.get("paths.content")).exists()
    assert Path(settings_instance.get("paths.downloads")).exists()
    assert Path(settings_instance.get("paths.backups")).exists()
    assert Path(settings_instance.get("paths.plugins")).exists()
    assert Path(settings_instance.get("paths.logs")).exists()

    # Test with a custom path not created by default init but by set
    custom_dir_path = Path(settings_instance.app_data_dir) / "custom_test_dir"
    assert not custom_dir_path.exists()
    settings_instance.set("paths.custom_test", str(custom_dir_path))
    # _ensure_dirs_exist is called on load, but if we add a new path type,
    # it's not automatically created by 'set'. This is expected.
    # The _ensure_dirs_exist is more about the core paths.
    # If a path is added to the "paths" section of default_config and then created,
    # it *would* be created by _ensure_dirs_exist upon next load.

    # Let's test if a new path added to the structure and then reloaded gets created
    # This means we need to modify the _settings directly for this test, or save and reload
    new_log_path_val = str(Path(settings_instance.app_data_dir) / ".new_logs")
    settings_instance._settings["paths"]["new_logs_test"] = new_log_path_val
    settings_instance._write_config()  # Write the modified config
    settings_instance.reload()  # Reload, which calls _ensure_dirs_exist

    # This test is a bit tricky because _ensure_dirs_exist only iterates specific keys.
    # A more robust test would involve mocking os.makedirs and checking calls.
    # For now, we rely on the explicit list in _ensure_dirs_exist.
    # The existing test for default paths is sufficient.


def test_settings_reload(settings_instance: Settings):
    """Test reloading settings from the config file."""
    settings_instance.set("web.port", 11111)  # Initial set

    config_file_path = Path(settings_instance.config_path)
    current_config = read_json_file(config_file_path)
    current_config["web"]["port"] = 22222
    current_config["custom"]["reloaded_val"] = True
    create_dummy_config(config_file_path, current_config)  # Simulate external change

    settings_instance.reload()

    assert settings_instance.get("web.port") == 22222
    assert settings_instance.get("custom.reloaded_val") is True


def test_settings_app_data_dir_override(tmp_path: Path, monkeypatch):
    """Test that BSM_DATA_DIR environment variable correctly overrides default app data dir."""
    custom_data_path = tmp_path / "custom_bsm_data"
    # No need to mkdir, Settings should do it.

    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(custom_data_path))
    settings = Settings()

    assert settings.app_data_dir == str(custom_data_path)
    assert settings.config_dir == str(custom_data_path / ".config")
    assert settings.config_path == str(
        custom_data_path / ".config" / NEW_CONFIG_FILE_NAME
    )
    assert custom_data_path.exists()
    assert (custom_data_path / ".config").exists()
    assert Path(settings.config_path).exists()


def test_settings_default_paths_without_env_override(tmp_path: Path, monkeypatch):
    """Test default path determination when BSM_DATA_DIR is not set."""
    # Ensure the env var is not set for this test
    monkeypatch.delenv(f"{env_name}_DATA_DIR", raising=False)

    # We need to control where the home directory is perceived to be for consistent testing
    # We'll patch os.path.expanduser for this test
    fake_home_dir = tmp_path / "fake_user_home"
    fake_home_dir.mkdir()

    original_expanduser = os.path.expanduser

    def mock_expanduser(path):
        if path == "~":
            return str(fake_home_dir)
        return original_expanduser(path)

    monkeypatch.setattr(os.path, "expanduser", mock_expanduser)

    settings = Settings()

    expected_data_dir = fake_home_dir / package_name
    assert settings.app_data_dir == str(expected_data_dir)
    assert settings.config_dir == str(expected_data_dir / ".config")
    assert (expected_data_dir / ".config" / NEW_CONFIG_FILE_NAME).exists()


def test_deep_merge():
    """Test the deep_merge utility function."""
    dest = {"a": 1, "b": {"c": 2, "d": 3, "x": {"y": 10}}, "f": 7}
    src = {"b": {"c": 5, "e": 6, "x": {"z": 20}}, "g": 8}

    merged = deep_merge(src, dest)

    assert merged["a"] == 1
    assert merged["b"]["c"] == 5  # Overwritten
    assert merged["b"]["d"] == 3  # Preserved
    assert merged["b"]["e"] == 6  # Added
    assert merged["b"]["x"]["y"] == 10  # Preserved nested
    assert merged["b"]["x"]["z"] == 20  # Added nested
    assert merged["f"] == 7
    assert merged["g"] == 8  # Added
    assert dest is merged  # Check modified in place

    # Test merging into a non-dict node
    dest2 = {"a": 1, "b": "not a dict"}
    src2 = {"b": {"c": 2}}
    merged2 = deep_merge(src2, dest2)
    assert merged2["b"]["c"] == 2

    # Test merging with empty source
    dest3 = {"a": 1}
    src3 = {}
    merged3 = deep_merge(src3, dest3)
    assert merged3["a"] == 1

    # Test merging with empty destination
    dest4 = {}
    src4 = {"a": 1}
    merged4 = deep_merge(src4, dest4)
    assert merged4["a"] == 1


def test_settings_load_corrupted_json(settings_instance: Settings, caplog):
    """Test loading a corrupted JSON config file."""
    config_file = Path(settings_instance.config_path)
    with open(config_file, "w") as f:
        f.write("this is not valid json")

    settings_instance.reload()  # Attempt to load corrupted file

    assert "Could not load config file" in caplog.text
    assert "Using default settings" in caplog.text
    # Check that settings are reset to defaults
    assert (
        settings_instance.get("retention.backups")
        == settings_instance.default_config["retention"]["backups"]
    )
    assert (
        settings_instance.get("web.port")
        == settings_instance.default_config["web"]["port"]
    )

    # Verify that a subsequent 'set' operation saves a valid default config
    settings_instance.set("web.threads", 8)
    assert settings_instance.get("web.threads") == 8
    try:
        loaded_settings = read_json_file(config_file)
        assert loaded_settings["web"]["threads"] == 8
        assert (
            loaded_settings["config_version"] == CONFIG_SCHEMA_VERSION
        )  # Should be a full valid config
    except json.JSONDecodeError:
        pytest.fail(
            "Config file was not rewritten with valid JSON after corruption and set operation."
        )


def test_config_file_permission_error_on_write(
    settings_instance: Settings, monkeypatch, caplog, tmp_path: Path
):
    """Test handling of permission errors when writing config file."""

    # Make the config file read-only to simulate permission issue for writing
    config_file_path = Path(settings_instance.config_path)

    # For this to work consistently, especially on POSIX, the directory needs to be writable
    # but the file itself not. If the directory is not writable, os.rename in migrate might fail first.
    # We will mock open to raise OSError for the write operation.

    original_open = open

    def mock_open_raise_oserror(file, mode="r", *args, **kwargs):
        if str(file) == str(config_file_path) and "w" in mode:
            raise OSError("Permission denied for testing")
        return original_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open_raise_oserror)

    with pytest.raises(
        ConfigurationError,
        match="Failed to write configuration: Permission denied for testing",
    ):
        settings_instance.set("web.port", 9999)  # This should attempt to write

    # Test that an error during initial _write_config in load (e.g. if file doesn't exist) is also handled.
    # For this, we need a fresh Settings instance where the file doesn't exist yet.

    # Create a scenario for a new Settings instance with a distinct app_data_dir
    # Use a sub-directory of tmp_path to ensure it's cleaned up
    app_data_for_new_instance = tmp_path / "new_instance_app_data"
    app_data_for_new_instance.mkdir(parents=True, exist_ok=True)

    # The Settings class will create ".config" inside this new app_data_dir.
    # We need to ensure this ".config" directory exists so that only open() fails.
    config_dir_for_new_instance = app_data_for_new_instance / ".config"
    config_dir_for_new_instance.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(app_data_for_new_instance))

    # Determine the config path that the *new* Settings instance will use
    expected_new_config_path = config_dir_for_new_instance / NEW_CONFIG_FILE_NAME

    # The mock_open_raise_oserror_multi is already set from the previous part of the test.
    # It needs to correctly identify this new expected_new_config_path.

    # We need a more targeted mock for the second part.
    # The previous mock_open_raise_oserror is specific to the settings_instance.
    # The mock_open_raise_oserror_multi was an attempt to combine them. Let's ensure it's correctly defined for this new path.
    # or make a new one if it's cleaner. For now, let's make it conditional.

    # Store original config_file_path for the first part of the test
    original_mocked_path = config_file_path

    def mock_open_raise_oserror_multi(file, mode="r", *args, **kwargs):
        # Case 1: For the settings_instance (first part of the test)
        if str(file) == str(original_mocked_path) and "w" in mode:
            raise OSError("Permission denied for testing (settings_instance)")
        # Case 2: For the new Settings() instance (second part of the test)
        elif str(file) == str(expected_new_config_path) and "w" in mode:
            raise OSError("Permission denied for testing (new Settings())")
        return original_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open_raise_oserror_multi)

    # Re-run the first part of the test with the new multi-mock
    # (This part was already passing, but good to ensure it still does)
    with pytest.raises(
        ConfigurationError,
        match=r"Failed to write configuration: Permission denied for testing \(settings_instance\)",
    ):
        settings_instance.set(
            "web.port", 9998
        )  # Use a different port to ensure 'set' runs

    # The Settings constructor calls load(), which calls _write_config() if file not found.
    with pytest.raises(
        ConfigurationError,
        match=r"Failed to write configuration: Permission denied for testing \(new Settings\(\)\)",
    ):
        Settings()


def test_config_file_migration_rename_error(tmp_config_dir: Path, monkeypatch, caplog):
    """Test handling of OSError during config filename migration."""
    caplog.set_level(logging.INFO)
    test_data_dir = tmp_config_dir / "test_migration_rename_fail"
    config_dir_path = test_data_dir / ".config"
    config_dir_path.mkdir(parents=True, exist_ok=True)

    old_config_file = config_dir_path / OLD_CONFIG_FILE_NAME
    new_config_file = config_dir_path / NEW_CONFIG_FILE_NAME  # Should not exist yet

    create_dummy_config(old_config_file, {"some_key": "some_value"})  # Old file exists

    original_rename = os.rename

    def mock_rename_raise_oserror(src, dst):
        if str(src) == str(old_config_file) and str(dst) == str(new_config_file):
            raise OSError("Permission denied for renaming (testing)")
        return original_rename(src, dst)

    monkeypatch.setattr(os, "rename", mock_rename_raise_oserror)
    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(test_data_dir))

    with pytest.raises(
        ConfigurationError, match=r"Failed to rename configuration file"
    ) as excinfo:
        Settings()

    assert "Failed to rename configuration file" in str(excinfo.value)
    assert old_config_file.exists()  # Old file should still be there
    assert (
        not new_config_file.exists()
    )  # New file should not have been created by rename


def test_v1_migration_backup_rename_error(tmp_config_dir: Path, monkeypatch, caplog):
    """Test handling of OSError during v1 config backup before migration."""
    caplog.set_level(logging.INFO)
    test_data_dir = tmp_config_dir / "test_v1_backup_fail"
    config_dir_path = test_data_dir / ".config"
    config_dir_path.mkdir(parents=True, exist_ok=True)

    config_file = (
        config_dir_path / NEW_CONFIG_FILE_NAME
    )  # V1 content, but new name (e.g. after filename migration)
    v1_content = {"BASE_DIR": "/v1/servers"}  # V1 content (no config_version)
    create_dummy_config(config_file, v1_content)

    backup_path = Path(str(config_file) + ".v1.bak")

    original_rename = os.rename

    def mock_rename_raise_oserror_for_backup(src, dst):
        if str(src) == str(config_file) and str(dst) == str(backup_path):
            raise OSError("Permission denied for v1 backup rename (testing)")
        return original_rename(src, dst)

    monkeypatch.setattr(os, "rename", mock_rename_raise_oserror_for_backup)
    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(test_data_dir))

    with pytest.raises(
        ConfigurationError, match=r"Failed to back up old config file"
    ) as excinfo:
        Settings()

    assert "Failed to back up old config file" in str(excinfo.value)
    assert config_file.exists()  # Original v1 file should still be there
    assert not backup_path.exists()  # Backup should not have been created
    # And settings should likely be default, or the process halted.
    # Check that the file content is still v1.
    current_content = read_json_file(config_file)
    assert "config_version" not in current_content
    assert current_content["BASE_DIR"] == "/v1/servers"


def test_ensure_dirs_permission_error(settings_instance: Settings, monkeypatch, caplog):
    """Test handling of OSError when creating critical directories."""
    caplog.set_level(logging.INFO)
    # We need to make one of the target directories unwritable by its parent.
    # This is hard to do without affecting other tests or requiring sudo.
    # A more common scenario is that os.makedirs itself fails.

    original_makedirs = os.makedirs
    failing_path = settings_instance.get("paths.logs")  # Pick one path to fail

    def mock_makedirs_raise_oserror(path, exist_ok=True):
        if str(Path(path)) == str(Path(failing_path)):
            raise OSError(f"Cannot create directory {path} (testing)")
        return original_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr(os, "makedirs", mock_makedirs_raise_oserror)

    # To trigger _ensure_dirs_exist, we reload.
    # However, settings_instance already called it in __init__.
    # We need a fresh instance or a way to force _ensure_dirs_exist.
    # Let's modify the path and reload.

    # Create a new settings instance in a new temp dir for this test
    # to ensure _ensure_dirs_exist is called in a controlled way.
    temp_dir_for_ensure_test = settings_instance.app_data_dir + "_ensure_fail"
    Path(temp_dir_for_ensure_test).mkdir(
        parents=True, exist_ok=True
    )  # Create the base app data dir

    # The .config dir inside it should NOT be created yet by this test setup,
    # so Settings() will try to create it, and then the log dir.

    monkeypatch.setenv(f"{env_name}_DATA_DIR", str(temp_dir_for_ensure_test))

    # The failing_path needs to be relative to this new data dir.
    # Re-calculate based on the new settings that will be created.
    expected_new_log_path = str(Path(temp_dir_for_ensure_test) / ".logs")

    # Adjust the mock_makedirs to use the correct path for this new instance
    def mock_makedirs_raise_oserror_specific(path, exist_ok=True):
        if str(Path(path)) == expected_new_log_path:
            raise OSError(f"Cannot create directory {path} (testing)")
        # Allow .config to be created
        elif str(Path(path)) == str(Path(temp_dir_for_ensure_test) / ".config"):
            return original_makedirs(path, exist_ok=exist_ok)
        return original_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr(os, "makedirs", mock_makedirs_raise_oserror_specific)

    with pytest.raises(
        ConfigurationError,
        match=rf"Could not create critical directory: {expected_new_log_path}",
    ) as excinfo:
        Settings()  # This will call _ensure_dirs_exist

    assert f"Could not create critical directory: {expected_new_log_path}" in str(
        excinfo.value
    )
