"""
Repository for managing Setting database entity persistence.
"""

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from ...state.validation import json_equal
from ..database import Database
from ..models import Setting


class SettingsRepository:
    """Handles database persistence for application settings."""

    def __init__(self, db: Database | None = None):
        self.db = db

    async def get_all_settings(self, session: AsyncSession) -> Dict[str, Any]:
        """Retrieves all settings as a dictionary of key-value pairs."""
        result = await session.execute(select(Setting))
        settings_records = result.scalars().all()
        return {str(record.key): record.value for record in settings_records}

    async def save_settings(
        self, session: AsyncSession, settings_dict: Dict[str, Any]
    ) -> None:
        """Persists a dictionary of key-value settings and removes obsolete flat dot-notation records."""
        for key, value in settings_dict.items():
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
            if "." in str(record.key):
                root_key = str(record.key).split(".")[0]
                if root_key in settings_dict and isinstance(
                    settings_dict[root_key], dict
                ):
                    await session.delete(record)
