"""
Integration tests for the API functions in bedrock_server_manager/api/plugins.py.
"""

from unittest.mock import patch

import pytest

from bedrock_server_manager.api.plugins import (
    get_plugin_statuses,
    reload_plugins,
    set_plugin_status,
    trigger_external_plugin_event_api,
)
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.error import UserInputError


def test_get_plugin_statuses_success(app_context: AppContext):
    """Test retrieving plugin statuses successfully."""
    # Mocking the internal methods
    with patch.object(
        app_context.plugin_manager, "_synchronize_config_with_disk"
    ) as mock_sync:
        app_context.plugin_manager.plugin_config = {
            "test_plugin": {"enabled": True, "version": "1.0.0"}
        }

        result = get_plugin_statuses(app_context)

        assert result["status"] == "success"
        assert "test_plugin" in result["plugins"]
        mock_sync.assert_called_once()


def test_set_plugin_status_success(app_context: AppContext):
    """Test setting plugin status successfully."""
    with patch.object(app_context.plugin_manager, "_synchronize_config_with_disk"):
        with patch.object(app_context.plugin_manager, "_save_config") as mock_save:
            app_context.plugin_manager.plugin_config = {
                "test_plugin": {"enabled": False}
            }

            result = set_plugin_status("test_plugin", True, app_context)

            assert result["status"] == "success"
            assert "test_plugin" in result["message"]
            assert (
                app_context.plugin_manager.plugin_config["test_plugin"]["enabled"]
                is True
            )
            mock_save.assert_called_once()


def test_set_plugin_status_not_found(app_context: AppContext):
    """Test setting plugin status for non-existent plugin raises UserInputError."""
    with patch.object(app_context.plugin_manager, "_synchronize_config_with_disk"):
        app_context.plugin_manager.plugin_config = {}

        with pytest.raises(UserInputError, match="not found"):
            set_plugin_status("unknown_plugin", True, app_context)


def test_set_plugin_status_empty_name(app_context: AppContext):
    """Test setting plugin status with empty name raises UserInputError."""
    with pytest.raises(UserInputError):
        set_plugin_status("", True, app_context)


def test_reload_plugins_success(app_context: AppContext):
    """Test reloading plugins successfully."""
    with patch.object(app_context.plugin_manager, "reload") as mock_reload:
        result = reload_plugins(app_context)

        assert result["status"] == "success"
        assert "reloaded successfully" in result["message"]
        mock_reload.assert_called_once()


def test_trigger_external_plugin_event_api_success(app_context: AppContext):
    """Test triggering external plugin event successfully."""
    with patch.object(
        app_context.plugin_manager, "trigger_custom_plugin_event"
    ) as mock_trigger:
        result = trigger_external_plugin_event_api(
            "test:event", app_context, {"data": 123}
        )

        assert result["status"] == "success"
        assert "test:event" in result["message"]
        mock_trigger.assert_called_once_with(
            "test:event", "external_api_trigger", data=123
        )


def test_trigger_external_plugin_event_api_empty_name(app_context: AppContext):
    """Test triggering event with empty name raises UserInputError."""
    with pytest.raises(UserInputError):
        trigger_external_plugin_event_api("", app_context)
