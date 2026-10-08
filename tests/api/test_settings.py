from unittest.mock import patch

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetAllGlobalSettingsRequest,
    GetGlobalSettingRequest,
    ReloadGlobalSettingsRequest,
    SetCustomGlobalSettingRequest,
    SetGlobalSettingRequest,
)
from bedrock_server_manager.api.settings import (
    get_all_global_settings,
    get_global_setting,
    reload_global_settings,
    set_custom_global_setting,
    set_global_setting,
)
from bedrock_server_manager.context import AppContext

"""
Integration tests for the API functions in bedrock_server_manager/api/settings.py.
"""


async def test_get_global_setting_success(app_context: AppContext):
    """Test retrieving a global setting successfully."""
    with patch.object(
        app_context.settings, "get", return_value="test_value"
    ) as mock_get:
        result = (
            await get_global_setting(
                request=GetGlobalSettingRequest(key="test_key"), app_context=app_context
            )
        ).model_dump(mode="python")

        assert result["status"] == "success"
        assert result["value"] == "test_value"
        mock_get.assert_called_once_with("test_key")


async def test_get_global_setting_empty_key(app_context: AppContext):
    """Test retrieving a setting with an empty key raises error."""
    with pytest.raises(ValidationError):
        (
            await get_global_setting(
                request=GetGlobalSettingRequest(key=""), app_context=app_context
            )
        ).model_dump(mode="python")


async def test_get_all_global_settings_success(app_context: AppContext):
    """Test retrieving all global settings successfully."""
    app_context.state.settings.set("key1", "value1")
    app_context.state.settings.set("key2", "value2")

    result = (
        await get_all_global_settings(
            request=GetAllGlobalSettingsRequest(), app_context=app_context
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert result["settings"]["custom"]["key1"] == "value1"
    assert result["settings"]["custom"]["key2"] == "value2"


async def test_set_global_setting_success(app_context: AppContext):
    """Test setting a global setting successfully."""
    with patch.object(app_context.settings, "set") as mock_set:
        result = (
            await set_global_setting(
                request=SetGlobalSettingRequest(key="test_key", value="new_value"),
                app_context=app_context,
            )
        ).model_dump(mode="python")

        assert result["status"] == "success"
        assert "test_key" in result["message"]
        mock_set.assert_called_once_with("test_key", "new_value")


async def test_set_global_setting_empty_key(app_context: AppContext):
    """Test setting a global setting with an empty key raises error."""
    with pytest.raises(ValidationError):
        (
            await set_global_setting(
                request=SetGlobalSettingRequest(key="", value="value"),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_set_custom_global_setting_success(app_context: AppContext):
    """Test setting a custom global setting successfully."""
    with patch.object(app_context.settings, "set") as mock_set:
        result = (
            await set_custom_global_setting(
                request=SetCustomGlobalSettingRequest(
                    key="test_key", value="custom_val"
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")

        assert result["status"] == "success"
        # custom. should be prepended
        assert "custom.test_key" in result["message"]
        mock_set.assert_called_once_with("custom.test_key", "custom_val")


async def test_reload_global_settings_success(app_context: AppContext):
    """Test reloading global settings successfully."""
    with patch.object(app_context, "reload") as mock_app_reload:
        with patch.object(app_context.settings, "reload") as mock_settings_reload:

            result = (
                await reload_global_settings(
                    request=ReloadGlobalSettingsRequest(), app_context=app_context
                )
            ).model_dump(mode="python")

            assert result["status"] == "success"
            mock_app_reload.assert_called_once()
            mock_settings_reload.assert_called_once()
