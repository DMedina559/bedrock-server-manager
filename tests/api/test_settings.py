import pytest

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
from bedrock_server_manager.error import UserInputError


async def test_global_settings_round_trip_through_database(app_context):
    await set_global_setting(
        SetGlobalSettingRequest(key="retention.downloads", value=7),
        app_context=app_context,
    )
    await set_custom_global_setting(
        SetCustomGlobalSettingRequest(key="integration", value={"nested": [1, True]}),
        app_context=app_context,
    )
    await reload_global_settings(ReloadGlobalSettingsRequest(), app_context=app_context)
    assert (
        await get_global_setting(
            GetGlobalSettingRequest(key="retention.downloads"), app_context=app_context
        )
    ).value == 7
    assert (
        await get_global_setting(
            GetGlobalSettingRequest(key="custom.integration"), app_context=app_context
        )
    ).value == {"nested": [1, True]}
    snapshot = await get_all_global_settings(
        GetAllGlobalSettingsRequest(), app_context=app_context
    )
    assert snapshot.settings["retention"]["downloads"] == 7


@pytest.mark.parametrize("value", [-1, "invalid", True])
async def test_invalid_setting_preserves_memory_and_database(app_context, value):
    original = app_context.settings.get("retention.downloads")
    with pytest.raises(UserInputError):
        await set_global_setting(
            SetGlobalSettingRequest(key="retention.downloads", value=value),
            app_context=app_context,
        )
    assert app_context.settings.get("retention.downloads") == original
    await reload_global_settings(ReloadGlobalSettingsRequest(), app_context=app_context)
    assert app_context.settings.get("retention.downloads") == original
