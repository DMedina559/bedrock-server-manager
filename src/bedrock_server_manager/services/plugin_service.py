# src/bedrock_server_manager/services/plugin_service.py
"""
Service managing plugin state mutations and configuration persistence.
"""

import copy
import json
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from pydantic import BaseModel, JsonValue, SecretStr, ValidationError
from pydantic_core import PydanticUndefined, to_jsonable_python

from ..server_validation import valid_server_names
from ..state.changeset import ChangeSet
from ..state.models import PluginInfoState
from ..state.updates import UNSET, PluginUpdate, Unset

if TYPE_CHECKING:
    from ..db.storage import Storage
    from ..state.app_state import AppState


def _json_settings(value):
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, BaseModel):
        return _json_settings(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {key: _json_settings(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_settings(item) for item in value]
    return to_jsonable_python(value)


class PluginService:
    """Handles domain logic and mutations for application plugins."""

    def __init__(
        self,
        state: "AppState",
        storage: "Storage",
    ):
        self.state = state
        self.storage = storage
        self.settings_models: dict[str, type[BaseModel]] = {}

    def get_settings(self, name: str) -> dict:
        values = self.state.settings.plugin_settings.get(name, {})
        model = self.settings_models.get(name)
        if model is not None:
            for key, field in model.model_fields.items():
                if key not in values:
                    default = field.get_default(call_default_factory=True)
                    if default is not PydanticUndefined:
                        values[key] = default
            # Convert enum/default factory values to the JSON contract.
            values = _json_settings(values)
        return values

    def get_settings_schema(self, name: str) -> dict | None:
        model = self.settings_models.get(name)
        if model is None:
            return None
        schema = model.model_json_schema()

        def choices(node):
            if isinstance(node, dict):
                if node.get("x-bsm-server-name"):
                    node["enum"] = valid_server_names(self.state)
                for child in node.values():
                    choices(child)
            elif isinstance(node, list):
                for child in node:
                    choices(child)

        choices(schema)
        return schema

    def validate_settings(self, name: str, values: dict) -> dict:
        from ..error import UserInputError

        model = self.settings_models.get(name)
        if model is None:
            return copy.deepcopy(values)
        try:
            return cast(
                dict,
                _json_settings(
                    model.model_validate_json(
                        json.dumps(values),
                        strict=True,
                        context={"server_names": valid_server_names(self.state)},
                    )
                ),
            )
        except ValidationError as error:
            raise UserInputError(
                f"Invalid settings for plugin '{name}'. Check field types and constraints."
            ) from error

    async def replace_settings(self, name: str, settings: dict) -> None:
        async with self.state.settings.get_lock("global"):
            values = self.state.settings.plugin_settings
            values[name] = self.validate_settings(name, settings)
            self.state.settings.set("plugin_settings", values)
        changeset = ChangeSet()
        changeset.add_setting("plugin_settings")
        await self.storage.apply_changeset(self.state, changeset)

    def get_plugin_state(self, plugin_name: str) -> Optional[PluginInfoState]:
        """Retrieves a plugin state model snapshot."""
        plugin = self.state.plugins.get(plugin_name)
        if plugin:
            res: PluginInfoState = plugin.model_copy()
            return res
        return None

    async def register_or_update_plugin(
        self,
        plugin_name: str,
        enabled: Optional[bool] = None,
        version: str | None | Unset = UNSET,
        author: str | None | Unset = UNSET,
        description: str | None | Unset = UNSET,
        settings: Optional[Dict[str, JsonValue]] = None,
    ) -> PluginInfoState:
        """Registers or updates a plugin state record and marks dirty state."""
        async with self.state.plugins.get_lock(plugin_name):
            existing = self.state.plugins.get(plugin_name)
            values: dict[str, object] = {"plugin_name": plugin_name}
            if enabled is not None:
                values["enabled"] = enabled
            elif existing is None:
                values["enabled"] = True
            for name, value in (
                ("version", version),
                ("author", author),
                ("description", description),
            ):
                if value is not UNSET:
                    values[name] = value
            update = PluginUpdate.model_validate(values)
            data = existing.model_dump() if existing else {}
            data.update(update.model_dump(exclude_unset=True))
            plugin = PluginInfoState.model_validate(data)

            changeset = ChangeSet()
            changeset.add_plugin(plugin_name)
            if settings is not None:
                async with self.state.settings.get_lock("global"):
                    values = self.state.settings.get("plugin_settings", {})
                    values[plugin_name] = self.validate_settings(plugin_name, settings)
                    candidate = self.state.settings.model_dump()
                    candidate["plugin_settings"] = values
                    type(self.state.settings).model_validate(candidate)
                    self.state.settings.set("plugin_settings", values)
                    self.state.plugins.set(plugin)
                changeset.add_setting("plugin_settings")
            else:
                self.state.plugins.set(plugin)

        await self.storage.apply_changeset(self.state, changeset)

        return plugin

    async def set_enabled(self, plugin_name: str, enabled: bool) -> None:
        """Enables or disables a plugin state."""
        await self.register_or_update_plugin(plugin_name, enabled=enabled)

    def get_setting(self, plugin_name: str, key: str):
        """Read only the calling plugin's persisted JSON settings."""
        value: Any = self.get_settings(plugin_name)
        for part in key.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    async def set_setting(self, plugin_name: str, key: str, value: JsonValue) -> None:
        from ..error import UserInputError

        parts = key.split(".")
        if any(not part or part.startswith("_") or "__" in part for part in parts):
            raise UserInputError("Invalid plugin setting key.")
        async with self.state.settings.get_lock("global"):
            values = self.state.settings.get("plugin_settings", {})
            values[plugin_name] = self.get_settings(plugin_name)
            current = values[plugin_name]
            for part in parts[:-1]:
                child = current.setdefault(part, {})
                if not isinstance(child, dict):
                    raise UserInputError("Plugin setting path conflicts with a value.")
                current = child
            current[parts[-1]] = value
            values[plugin_name] = self.validate_settings(
                plugin_name, values[plugin_name]
            )
            self.state.settings.set("plugin_settings", values)
        changeset = ChangeSet()
        changeset.add_setting("plugin_settings")
        await self.storage.apply_changeset(self.state, changeset)
