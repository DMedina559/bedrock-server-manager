"""
Repository for managing Plugin database entity persistence.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.future import select

from ...state.models import PluginInfoState
from ..models import Plugin


class PluginRepository:
    """Handles database persistence for plugin configurations."""

    def __init__(self, db: Any = None):
        self.db = db

    async def get_all_plugins(
        self,
        session: Any,
        plugin_settings_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[PluginInfoState]:
        """Retrieves all plugins from the database as PluginInfoState models."""
        if plugin_settings_map is None:
            plugin_settings_map = {}
        result = await session.execute(select(Plugin))
        plugins = []
        for p in result.scalars().all():
            p_name = str(p.plugin_name)
            p_info = PluginInfoState(
                plugin_name=p_name,
                enabled=bool(p.enabled),
                version=str(p.version) if p.version else None,
                author=str(p.author) if p.author else None,
                description=str(p.description) if p.description else None,
                settings=plugin_settings_map.get(p_name, {}),
            )
            plugins.append(p_info)
        return plugins

    async def save_plugin(self, session: Any, p_info: PluginInfoState) -> None:
        """Persists or updates a single PluginInfoState record."""
        result = await session.execute(
            select(Plugin).filter_by(plugin_name=p_info.plugin_name)
        )
        plugin_record = result.scalars().first()
        if plugin_record:
            plugin_record.enabled = p_info.enabled
            plugin_record.version = p_info.version
            plugin_record.author = p_info.author
            plugin_record.description = p_info.description
        else:
            plugin_record = Plugin(
                plugin_name=p_info.plugin_name,
                enabled=p_info.enabled,
                version=p_info.version,
                author=p_info.author,
                description=p_info.description,
            )
            session.add(plugin_record)
