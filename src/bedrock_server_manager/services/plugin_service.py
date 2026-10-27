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
    """Handle domain logic and mutations for application plugins."""

    def __init__(
        self,
        state: "AppState",
        storage: "Storage",
    ):
        self.state = state
        self.storage = storage
        self.settings_models: dict[str, type[BaseModel]] = {}
        self.global_settings_models: dict[str, type[BaseModel]] = {}
        self.server_settings_models: dict[str, type[BaseModel]] = {}
        storage.custom_settings_validator = self.validate_custom

    def _models(self, scope: str) -> dict[str, type[BaseModel]]:
        from ..error import UserInputError

        if scope not in ("plugin", "global", "server"):
            raise UserInputError("Unknown plugin settings scope")
        return {
            "plugin": self.settings_models,
            "global": self.global_settings_models,
            "server": self.server_settings_models,
        }[scope]

    def _server(self, server_name):
        from ..error import UserInputError

        record = self.state.servers.get(server_name) if server_name else None
        if record is None:
            raise UserInputError("Choose an existing server")
        return record

    def get_settings(self, name: str, scope="plugin", server_name=None) -> dict:
        from ..error import UserInputError

        model = self._models(scope).get(name)
        if scope == "plugin":
            raw: Any = self.state.settings.plugin_settings.get(name, {})
        else:
            if model is None:
                raise UserInputError("Plugin does not declare this settings scope")
            custom = (
                self._server(server_name).custom
                if scope == "server"
                else self.state.settings.custom
            )
            raw = custom.get(name, {})
        if not isinstance(raw, dict):
            raise UserInputError("Plugin settings namespace must contain an object")
        values = copy.deepcopy(raw)
        if model is not None:
            for key, field in model.model_fields.items():
                if key not in values:
                    default = field.get_default(
                        call_default_factory=True, validated_data=values
                    )
                    if default is not PydanticUndefined:
                        values[key] = default
            # Convert enum/default factory values to the JSON contract.
            values = _json_settings(values)
        return values

    def get_settings_schema(self, name: str, scope="plugin") -> dict | None:
        model = self._models(scope).get(name)
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

    def validate_settings(
        self, name: str, values: dict, scope="plugin", server_name=None
    ) -> dict:
        from ..error import UserInputError

        model = self._models(scope).get(name)
        if model is None:
            return copy.deepcopy(values)
        try:
            return cast(
                dict,
                _json_settings(
                    model.model_validate_json(
                        json.dumps(values),
                        strict=True,
                        context={
                            "server_names": valid_server_names(self.state),
                            "server_name": server_name,
                            "plugin_name": name,
                        },
                    )
                ),
            )
        except ValidationError as error:
            fields = ", ".join(
                ".".join(str(part) for part in item["loc"]) or "settings"
                for item in error.errors(include_input=False, include_context=False)[
                    :10
                ]
            )
            raise UserInputError(
                f"Invalid settings for plugin '{name}'. Check: {fields}."
            ) from error

    def validate_custom(self, scope, before, after, server_name=None):
        from ..error import UserInputError
        from ..state.validation import json_equal

        checked = copy.deepcopy(after)
        for name in self._models(scope):
            if name not in checked or (
                name in before and json_equal(before[name], checked[name])
            ):
                continue
            if not isinstance(checked[name], dict):
                raise UserInputError(f"Plugin '{name}' settings must contain an object")
            checked[name] = self.validate_settings(
                name, checked[name], scope, server_name
            )
        return checked

    async def replace_settings(
        self, name: str, settings: dict, scope="plugin", server_name=None
    ) -> None:
        if scope != "plugin":
            # Validate before entering the normal storage transaction; the boundary
            # validates again against the latest committed namespace.
            from ..error import UserInputError

            if self._models(scope).get(name) is None:
                raise UserInputError("Plugin does not declare this settings scope")
            if scope == "server":
                self._server(server_name)
            checked = self.validate_settings(name, settings, scope, server_name)
            if scope == "global":
                from .settings_service import SettingsService

                await SettingsService(
                    self.state, self.storage, plugin_service=self
                ).update_setting(f"custom.{name}", checked)
            else:
                from .server_service import ServerService

                await ServerService(self.state, self.storage).update_setting(
                    server_name, f"custom.{name}", checked
                )
            return

        def mutate(candidate):
            values = candidate.plugin_settings
            values[name] = self.validate_settings(name, settings)
            candidate.set("plugin_settings", values)

        changeset = ChangeSet()
        changeset.add_setting("plugin_settings")
        await self.storage.commit_settings(self.state, changeset, mutate)

    def get_plugin_state(self, plugin_name: str) -> Optional[PluginInfoState]:
        """Return a plugin state model snapshot."""
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
        """Register or updates a plugin state record and marks dirty state."""
        values: dict[str, object] = {"plugin_name": plugin_name}
        if enabled is not None:
            values["enabled"] = enabled
        for name, value in (
            ("version", version),
            ("author", author),
            ("description", description),
        ):
            if value is not UNSET:
                values[name] = value
        return await self.apply_update(
            PluginUpdate.model_validate(values), settings=settings
        )

    async def apply_update(
        self, request: PluginUpdate, *, settings: dict[str, JsonValue] | None = None
    ) -> PluginInfoState:
        request = PluginUpdate.model_validate(request)
        name = request.plugin_name
        changeset = ChangeSet()
        changeset.add_plugin(name)
        async with self.storage.write_lock:
            async with self.state.plugins.get_lock(name):
                async with self.state.settings.get_lock("global"):
                    existing = self.state.plugins.get(name)
                    data = existing.model_dump() if existing else {"enabled": True}
                    data.update(request.model_dump(exclude_unset=True))
                    plugin = PluginInfoState.model_validate(data)
                    candidate = None
                    if settings is not None:
                        candidate = type(self.state.settings).model_validate(
                            self.state.settings.model_dump()
                        )
                        values = candidate.plugin_settings
                        values[name] = self.validate_settings(name, settings)
                        candidate.set("plugin_settings", values)
                        changeset.add_setting("plugin_settings")
                    async with self.storage.transaction() as session:
                        await self.storage.plugin_repo.save_plugin(session, plugin)
                        if candidate is not None:
                            await self.storage.settings_repo.save_settings(
                                session, candidate.to_dict()
                            )
                    self.state.plugins.set(plugin)
                    self.state.plugins.remove_dirty_plugin(name)
                    if candidate is not None:
                        candidate.clear_dirty()
                        self.state.settings = candidate
        await self.storage._notify_listeners(self.state, changeset)
        return plugin

    async def set_enabled(self, plugin_name: str, enabled: bool) -> None:
        """Enables or disables a plugin state."""
        await self.register_or_update_plugin(plugin_name, enabled=enabled)

    def get_setting(
        self, plugin_name: str, key: str | None, scope="plugin", server_name=None
    ):
        """Read only the calling plugin's persisted JSON settings."""
        value: Any = self.get_settings(plugin_name, scope, server_name)
        if key is None:
            return value
        for part in key.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    async def set_setting(
        self,
        plugin_name: str,
        key: str | None,
        value: JsonValue,
        scope="plugin",
        server_name=None,
    ) -> None:
        from ..error import UserInputError

        if key is None:
            if not isinstance(value, dict):
                raise UserInputError("Plugin settings must contain an object")
            await self.replace_settings(plugin_name, value, scope, server_name)
            return
        parts = key.split(".")
        if any(not part or part.startswith("_") or "__" in part for part in parts):
            raise UserInputError("Invalid plugin setting key.")

        if scope != "plugin":
            # Apply a field update inside the transaction to avoid losing sibling writes.
            self.get_settings(plugin_name, scope, server_name)
            if scope == "global":
                from .settings_service import SettingsService

                await SettingsService(
                    self.state, self.storage, plugin_service=self
                ).update_setting(f"custom.{plugin_name}.{key}", value)
            else:
                from .server_service import ServerService

                await ServerService(self.state, self.storage).update_setting(
                    server_name, f"custom.{plugin_name}.{key}", value
                )
            return

        def mutate(candidate):
            values = candidate.get("plugin_settings", {})
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
            candidate.set("plugin_settings", values)

        changeset = ChangeSet()
        changeset.add_setting("plugin_settings")
        await self.storage.commit_settings(self.state, changeset, mutate)
