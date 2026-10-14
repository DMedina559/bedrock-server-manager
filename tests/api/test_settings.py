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


async def test_monitoring_defaults_and_live_intervals_persist(app_context):
    defaults = app_context.settings.default_config
    assert defaults["monitoring"]["app_metrics_interval_sec"] == 3
    assert defaults["monitoring"]["bedrock_metrics_interval_sec"] == 3
    assert defaults["lifecycle"]["startup_timeout_seconds"] == 30
    for key, value in (
        ("monitoring.app_metrics_interval_sec", 5),
        ("monitoring.bedrock_metrics_interval_sec", 7),
        ("lifecycle.startup_timeout_seconds", 45.0),
    ):
        await set_global_setting(
            SetGlobalSettingRequest(key=key, value=value), app_context=app_context
        )
    assert app_context.metrics_service.interval_seconds == 5
    assert (await app_context.metrics_service.snapshot()).interval_seconds == 5
    assert app_context.resource_monitor.interval_provider() == 7
    await reload_global_settings(ReloadGlobalSettingsRequest(), app_context=app_context)
    assert app_context.settings.get("lifecycle.startup_timeout_seconds") == 45.0
    assert app_context.settings.get("monitoring.app_metrics_interval_sec") == 5
    assert app_context.settings.get("monitoring.bedrock_metrics_interval_sec") == 7


@pytest.mark.parametrize("value", [0, -1, 3601, 1.5, "3", True])
@pytest.mark.parametrize(
    "name", ["app_metrics_interval_sec", "bedrock_metrics_interval_sec"]
)
async def test_metric_interval_rejects_invalid_values(app_context, name, value):
    key = f"monitoring.{name}"
    with pytest.raises(UserInputError):
        await set_global_setting(
            SetGlobalSettingRequest(key=key, value=value), app_context=app_context
        )
    assert app_context.settings.get(key) == 3
