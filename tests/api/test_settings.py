"""
Integration tests for the API functions in bedrock_server_manager/api/settings.py.
"""

from unittest.mock import patch

import pytest

from bedrock_server_manager.api.settings import (
    get_all_global_settings,
    get_global_setting,
    reload_global_settings,
    set_custom_global_setting,
    set_global_setting,
)
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.error import MissingArgumentError


def test_get_global_setting_success(app_context: AppContext):
    """Test retrieving a global setting successfully."""
    with patch.object(
        app_context.settings, "get", return_value="test_value"
    ) as mock_get:
        result = get_global_setting("test_key", app_context)

        assert result["status"] == "success"
        assert result["value"] == "test_value"
        mock_get.assert_called_once_with("test_key")


def test_get_global_setting_empty_key(app_context: AppContext):
    """Test retrieving a setting with an empty key raises error."""
    with pytest.raises(MissingArgumentError):
        get_global_setting("", app_context)


def test_get_all_global_settings_success(app_context: AppContext):
    """Test retrieving all global settings successfully."""
    app_context.settings._settings = {"key1": "value1", "key2": "value2"}

    result = get_all_global_settings(app_context)

    assert result["status"] == "success"
    assert result["key1"] == "value1"
    assert result["key2"] == "value2"


def test_set_global_setting_success(app_context: AppContext):
    """Test setting a global setting successfully."""
    with patch.object(app_context.settings, "set") as mock_set:
        result = set_global_setting("test_key", "new_value", app_context)

        assert result["status"] == "success"
        assert "test_key" in result["message"]
        mock_set.assert_called_once_with("test_key", "new_value")


def test_set_global_setting_empty_key(app_context: AppContext):
    """Test setting a global setting with an empty key raises error."""
    with pytest.raises(MissingArgumentError):
        set_global_setting("", "value", app_context)


def test_set_custom_global_setting_success(app_context: AppContext):
    """Test setting a custom global setting successfully."""
    with patch.object(app_context.settings, "set") as mock_set:
        result = set_custom_global_setting("test_key", "custom_val", app_context)

        assert result["status"] == "success"
        # custom. should be prepended
        assert "custom.test_key" in result["message"]
        mock_set.assert_called_once_with("custom.test_key", "custom_val")


def test_reload_global_settings_success(app_context: AppContext):
    """Test reloading global settings successfully."""
    with patch.object(app_context, "reload") as mock_app_reload:
        with patch.object(app_context.settings, "reload") as mock_settings_reload:
            with patch.object(
                app_context.settings, "get", side_effect=["/logs", 10, "INFO"]
            ):
                with patch(
                    "bedrock_server_manager.api.settings.setup_logging"
                ) as mock_setup_logging:
                    result = reload_global_settings(app_context)

                    assert result["status"] == "success"
                    mock_app_reload.assert_called_once()
                    mock_settings_reload.assert_called_once()
                    mock_setup_logging.assert_called_once_with(
                        log_dir="/logs",
                        log_keep=10,
                        log_level="INFO",
                        force_reconfigure=True,
                    )
