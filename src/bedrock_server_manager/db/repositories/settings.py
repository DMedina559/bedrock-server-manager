"""
Repository for managing Setting database entity persistence.
"""

from typing import Any, Dict

from sqlalchemy.future import select

from ..models import Setting


class SettingsRepository:
    """Handles database persistence for application settings."""

    def __init__(self, db: Any = None):
        self.db = db

    async def get_all_settings(self, session: Any) -> Dict[str, Any]:
        """Retrieves all settings as a dictionary of key-value pairs."""
        result = await session.execute(select(Setting))
        settings_records = result.scalars().all()
        return {str(record.key): record.value for record in settings_records}

    async def save_settings(self, session: Any, settings_dict: Dict[str, Any]) -> None:
        """Persists a dictionary of key-value settings and removes obsolete flat dot-notation records."""
        for key, value in settings_dict.items():
            result = await session.execute(select(Setting).filter_by(key=key))
            setting = result.scalars().first()
            if setting:
                setting.value = value
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
