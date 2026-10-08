from unittest.mock import patch

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetPluginStatusesRequest,
    ReloadPluginsRequest,
    SetPluginStatusRequest,
    TriggerExternalAppEventRequest,
)
from bedrock_server_manager.api.plugins import (
    get_plugin_statuses,
    reload_plugins,
    set_plugin_status,
    trigger_external_app_event,
)
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.error import UserInputError

"""
Integration tests for the API functions in bedrock_server_manager/api/plugins.py.
"""


async def test_get_plugin_statuses_success(app_context: AppContext):
    """Test retrieving plugin statuses successfully."""
    # Mocking the internal methods
    with patch.object(
        app_context.plugin_manager, "_synchronize_config_with_disk"
    ) as mock_sync:
        app_context.plugin_manager.plugin_config = {
            "test_plugin": {"enabled": True, "version": "1.0.0"}
        }

        result = (
            await get_plugin_statuses(
                request=GetPluginStatusesRequest(), app_context=app_context
            )
        ).model_dump(mode="python")

        assert result["status"] == "success"
        assert "test_plugin" in result["plugins"]
        mock_sync.assert_called_once()


async def test_set_plugin_status_success(app_context: AppContext):
    """Test setting plugin status successfully."""
    with patch.object(app_context.plugin_manager, "_synchronize_config_with_disk"):
        with (
            patch.object(app_context.plugin_manager, "_save_config") as mock_save,
            patch.object(
                app_context.plugin_manager, "load_plugin_by_name", return_value=True
            ),
        ):
            app_context.plugin_manager.plugin_config = {
                "test_plugin": {"enabled": False}
            }

            result = (
                await set_plugin_status(
                    request=SetPluginStatusRequest(
                        target_plugin_name="test_plugin", enabled=True
                    ),
                    app_context=app_context,
                )
            ).model_dump(mode="python")

            assert result["status"] == "success"
            assert "test_plugin" in result["message"]
            assert (
                app_context.plugin_manager.plugin_config["test_plugin"]["enabled"]
                is True
            )
            mock_save.assert_called_once()


async def test_set_plugin_status_not_found(app_context: AppContext):
    """Test setting plugin status for non-existent plugin raises UserInputError."""
    with patch.object(app_context.plugin_manager, "_synchronize_config_with_disk"):
        app_context.plugin_manager.plugin_config = {}

        with pytest.raises(UserInputError, match="not found"):
            (
                await set_plugin_status(
                    request=SetPluginStatusRequest(
                        target_plugin_name="unknown_plugin", enabled=True
                    ),
                    app_context=app_context,
                )
            ).model_dump(mode="python")


async def test_set_plugin_status_empty_name(app_context: AppContext):
    """Test setting plugin status with empty name raises UserInputError."""
    with pytest.raises(ValidationError):
        (
            await set_plugin_status(
                request=SetPluginStatusRequest(target_plugin_name="", enabled=True),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_reload_plugins_success(app_context: AppContext):
    """Test reloading plugins successfully."""
    with patch.object(app_context.plugin_manager, "reload") as mock_reload:
        result = (
            await reload_plugins(
                request=ReloadPluginsRequest(), app_context=app_context
            )
        ).model_dump(mode="python")

        assert result["status"] == "success"
        assert "reloaded successfully" in result["message"]
        mock_reload.assert_called_once()


async def test_trigger_external_app_event_success(app_context: AppContext):
    """Test triggering external plugin event successfully."""
    with patch.object(app_context.plugin_manager, "trigger_event") as mock_trigger:
        result = (
            await trigger_external_app_event(
                request=TriggerExternalAppEventRequest(
                    event_name="test:event", payload={"data": 123}
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")

        assert result["status"] == "success"
        assert "test:event" in result["message"]
        mock_trigger.assert_called_once_with(
            "test:event", data=123, _triggering_plugin="external_api_trigger"
        )


async def test_trigger_external_app_event_empty_name(app_context: AppContext):
    """Test triggering event with empty name raises UserInputError."""
    with pytest.raises(ValidationError):
        (
            await trigger_external_app_event(
                request=TriggerExternalAppEventRequest(event_name=""),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_failed_enable_does_not_report_success(app_context):
    from unittest.mock import AsyncMock

    from bedrock_server_manager.error import BSMError

    manager = app_context.plugin_manager
    manager.plugin_config = {"sample": {"enabled": False}}
    with (
        patch.object(manager, "_synchronize_config_with_disk", AsyncMock()),
        patch.object(manager, "enable_plugin", AsyncMock(return_value=False)),
    ):
        with pytest.raises(BSMError):
            await set_plugin_status(
                SetPluginStatusRequest(target_plugin_name="sample", enabled=True),
                app_context=app_context,
            )
