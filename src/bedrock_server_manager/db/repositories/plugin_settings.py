"""Persistence for settings owned by individual plugins."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ...state.models import json_equal
from ..models import PluginSetting


class PluginSettingsRepository:
    async def get_all(self, session: AsyncSession) -> dict[str, dict[str, Any]]:
        records = (await session.execute(select(PluginSetting))).scalars().all()
        return {record.plugin_name: record.settings for record in records}

    async def save(
        self, session: AsyncSession, settings: dict[str, dict[str, Any]]
    ) -> None:
        """Replace the plugin settings snapshot inside the caller's transaction."""
        records = {
            record.plugin_name: record
            for record in (await session.execute(select(PluginSetting))).scalars().all()
        }
        for name, values in settings.items():
            record = records.pop(name, None)
            if record is None:
                session.add(PluginSetting(plugin_name=name, settings=values))
            elif not json_equal(record.settings, values):
                record.settings = values
                flag_modified(record, "settings")
        for record in records.values():
            await session.delete(record)
