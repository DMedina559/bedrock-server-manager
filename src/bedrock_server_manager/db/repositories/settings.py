"""
Repository for managing Setting database entity persistence.
"""

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from ...state.models import json_equal
from ..models import Setting
from .plugin_settings import PluginSettingsRepository


class SettingsRepository:
    """Handle database persistence for application settings."""

    def __init__(self):
        self.plugin_settings = PluginSettingsRepository()

    async def remove_obsolete_player_interval(self, session: AsyncSession) -> bool:
        """Remove the retired polling key from section JSON and legacy flat rows."""
        result = await session.execute(
            select(Setting).where(
                Setting.key.in_(("monitoring", "monitoring.player_interval_sec"))
            )
        )
        changed = False
        for record in result.scalars():
            if record.key == "monitoring.player_interval_sec":
                await session.delete(record)
                changed = True
            elif (
                isinstance(record.value, dict) and "player_interval_sec" in record.value
            ):
                record.value = {
                    key: value
                    for key, value in record.value.items()
                    if key != "player_interval_sec"
                }
                flag_modified(record, "value")
                changed = True
        return changed

    async def get_all_settings(self, session: AsyncSession) -> Dict[str, Any]:
        """Return all settings as a dictionary of key-value pairs."""
        result = await session.execute(select(Setting))
        settings_records = result.scalars().all()
        values: Dict[str, Any] = {
            str(record.key): record.value for record in settings_records
        }
        plugin_values = await self.plugin_settings.get_all(session)
        if plugin_values:
            values["plugin_settings"] = plugin_values
        return values

    async def save_settings(
        self, session: AsyncSession, settings_dict: Dict[str, Any]
    ) -> None:
        """Persists a dictionary of key-value settings and removes obsolete flat dot-notation records."""
        if "plugin_settings" in settings_dict:
            await self.plugin_settings.save(session, settings_dict["plugin_settings"])
        for key, value in settings_dict.items():
            if key == "plugin_settings" or key.startswith("plugin_settings."):
                continue
            result = await session.execute(select(Setting).filter_by(key=key))
            setting = result.scalars().first()
            if setting:
                if not json_equal(setting.value, value):
                    setting.value = value
                    # JSON's default ORM comparison treats 1 and True as equal.
                    flag_modified(setting, "value")
            else:
                setting = Setting(key=key, value=value)
                session.add(setting)

        # Clean up legacy flat dot-notation keys ONLY if corresponding section is saved as a dictionary
        result = await session.execute(select(Setting))
        all_records = result.scalars().all()
        for record in all_records:
            if record.key == "plugin_settings" or str(record.key).startswith(
                "plugin_settings."
            ):
                await session.delete(record)
                continue
            if "." in str(record.key):
                root_key = str(record.key).split(".")[0]
                if root_key in settings_dict and isinstance(
                    settings_dict[root_key], dict
                ):
                    await session.delete(record)
