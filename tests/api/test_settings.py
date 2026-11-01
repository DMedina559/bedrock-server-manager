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


async def test_global_settings_round_trip_monitoring_and_validation(app_context):
    # Defaults check
    defaults = app_context.settings.default_config
    assert defaults["monitoring"]["app_metrics_interval_sec"] == 3
    assert defaults["monitoring"]["bedrock_metrics_interval_sec"] == 3
    assert defaults["lifecycle"]["startup_timeout_seconds"] == 30

    # Invalid settings preserve memory and database
    original_downloads = app_context.settings.get("retention.downloads")
    for bad_val in (-1, "invalid", True):
        with pytest.raises(UserInputError):
            await set_global_setting(
                SetGlobalSettingRequest(key="retention.downloads", value=bad_val),
                app_context=app_context,
            )
        assert app_context.settings.get("retention.downloads") == original_downloads

    for name in ("app_metrics_interval_sec", "bedrock_metrics_interval_sec"):
        key = f"monitoring.{name}"
        for bad_val in (0, -1, 3601, 1.5, "3", True):
            with pytest.raises(UserInputError):
                await set_global_setting(
                    SetGlobalSettingRequest(key=key, value=bad_val),
                    app_context=app_context,
                )
            assert app_context.settings.get(key) == 3

    # Valid round trip and live intervals
    await set_global_setting(
        SetGlobalSettingRequest(key="retention.downloads", value=7),
        app_context=app_context,
    )
    await set_custom_global_setting(
        SetCustomGlobalSettingRequest(key="integration", value={"nested": [1, True]}),
        app_context=app_context,
    )
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
    assert app_context.settings.get("lifecycle.startup_timeout_seconds") == 45.0
    assert app_context.settings.get("monitoring.app_metrics_interval_sec") == 5
    assert app_context.settings.get("monitoring.bedrock_metrics_interval_sec") == 7

    snapshot = await get_all_global_settings(
        GetAllGlobalSettingsRequest(), app_context=app_context
    )
    assert snapshot.settings["retention"]["downloads"] == 7
