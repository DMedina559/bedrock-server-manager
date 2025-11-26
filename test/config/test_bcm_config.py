# test/config/test_bcm_config.py
import os
import json
from unittest.mock import patch
from bedrock_server_manager.config import bcm_config

# Test data
CONFIG_DATA = {"data_dir": "/test/data", "db_url": "sqlite:////test/data/.config/bedrock-server-manager.db"}

@patch("os.path.exists")
@patch("builtins.open")
@patch("json.load")
@patch.dict(os.environ, {}, clear=True)
def test_load_config_from_file(mock_json_load, mock_open, mock_exists):
    """Verify that the config is loaded from the file when no env vars are set."""
    mock_exists.return_value = True
    mock_json_load.return_value = CONFIG_DATA
    
    config = bcm_config.load_config()
    
    assert config["data_dir"] == CONFIG_DATA["data_dir"]
    assert config["db_url"] == CONFIG_DATA["db_url"]

@patch("os.path.exists")
@patch("builtins.open")
@patch("json.load")
@patch.dict(os.environ, {"BSM_DATA_DIR": "/env/data"}, clear=True)
def test_load_config_data_dir_from_env(mock_json_load, mock_open, mock_exists):
    """Verify that BSM_DATA_DIR overrides the config file."""
    mock_exists.return_value = True
    mock_json_load.return_value = CONFIG_DATA
    
    config = bcm_config.load_config()
    
    assert config["data_dir"] == "/env/data"
    assert config["db_url"] == CONFIG_DATA["db_url"]

@patch("os.path.exists")
@patch("builtins.open")
@patch("json.load")
@patch.dict(os.environ, {"BSM_DB_URL": "sqlite:////env/data/db.sqlite"}, clear=True)
def test_load_config_db_url_from_env(mock_json_load, mock_open, mock_exists):
    """Verify that BSM_DB_URL overrides the config file."""
    mock_exists.return_value = True
    mock_json_load.return_value = CONFIG_DATA
    
    config = bcm_config.load_config()
    
    assert config["data_dir"] == CONFIG_DATA["data_dir"]
    assert config["db_url"] == "sqlite:////env/data/db.sqlite"

@patch("os.path.exists")
@patch("builtins.open")
@patch("json.load")
@patch.dict(os.environ, {"BSM_DATA_DIR": "/env/data", "BSM_DB_URL": "sqlite:////env/data/db.sqlite"}, clear=True)
def test_load_config_all_from_env(mock_json_load, mock_open, mock_exists):
    """Verify that both environment variables override the config file."""
    mock_exists.return_value = True
    mock_json_load.return_value = CONFIG_DATA
    
    config = bcm_config.load_config()
    
    assert config["data_dir"] == "/env/data"
    assert config["db_url"] == "sqlite:////env/data/db.sqlite"

@patch("os.path.exists")
@patch("os.path.expanduser")
@patch("os.makedirs")
@patch("builtins.open")
@patch("json.dump")
@patch.dict(os.environ, {}, clear=True)
def test_load_config_defaults(mock_json_dump, mock_open, mock_makedirs, mock_expanduser, mock_exists):
    """Verify that default values are used when no config file or env vars are present."""
    mock_exists.return_value = False
    mock_expanduser.return_value = "/home/user"
    
    config = bcm_config.load_config()
    
    assert config["data_dir"] == f"/home/user/{bcm_config.package_name}"
    assert "sqlite:///" in config["db_url"]
    assert config["db_url"].endswith(".config/bedrock-server-manager.db")

@patch("os.path.exists")
@patch("builtins.open")
@patch("json.load")
@patch("os.makedirs")
@patch("json.dump")
@patch.dict(os.environ, {"BSM_DATA_DIR": "/env/data"}, clear=True)
def test_env_vars_not_saved_to_config(mock_json_dump, mock_makedirs, mock_json_load, mock_open, mock_exists):
    """Verify that environment variable values are not saved back to the config file."""
    mock_exists.return_value = True
    # Simulate a config file that's missing the db_url
    mock_json_load.return_value = {"data_dir": "/file/data"}

    bcm_config.load_config()
    
    # Check what was passed to json.dump
    args, kwargs = mock_json_dump.call_args
    saved_config = args[0]
    
    # It should not have saved the environment variable value
    assert saved_config["data_dir"] != "/env/data"
    # It should have saved the original file value
    assert saved_config["data_dir"] == "/file/data"
