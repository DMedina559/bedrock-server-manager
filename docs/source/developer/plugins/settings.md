# Plugin Settings and Storage

## Managing Configuration

Plugins often need to store configuration data persistently.

### 1. Isolated Plugin Settings

Bedrock Server Manager provides built-in methods on `PluginBase` to safely read and write your plugin's configuration to the database without conflicting with other plugins or core settings. This data is stored globally for your plugin.

*   **Saving Data:** `await self.set_plugin_setting(key="my_setting", value="my_value")`
*   **Loading Data:** `await self.get_plugin_setting(key="my_setting", default="default_value")`

```python
from bedrock_server_manager import app_event, PluginBase

class MyConfigurablePlugin(PluginBase):
    version = "4.0.0"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        # Load existing settings or set defaults asynchronously
        self.plugin_config = await self.get_plugin_setting("config", default={"enable_feature_x": True})

        if "api_key" not in self.plugin_config:
            self.logger.info("Initializing defaults.")
            self.plugin_config["api_key"] = "YOUR_KEY_HERE"

            # Save the updated configuration
            await self.set_plugin_setting("config", self.plugin_config)

        self.logger.info(f"Loaded config: {self.plugin_config}")
```

### 2. Custom Global Application Settings

If you need to store global settings outside of your plugin's isolated namespace, you can use the custom global setting API. These are stored in the database under the `custom.` namespace.

*   **Saving Data:** `await self.api.settings.set_custom_global_setting({"key": "my_global_key", "value": "my_value"})`
*   **Loading Data:** `await self.api.settings.get_global_setting({"key": "custom.my_global_key"})`

### 3. Server-Specific Custom Settings

You can also store custom settings that apply only to a specific Minecraft server.

*   **Saving Server Data:** `await self.api.server.set_custom_value({"server_name": "survival_world", "key": "some_key", "value": "some_value"})`
*   **Loading Server Data:** `await self.api.server.get_setting({"server_name": "survival_world", "key": "custom.some_key"})`

API reads return a response model; read its `.value` attribute. Settings contain
JSON values. Changing a returned dictionary does not save it; call the setter
explicitly after editing your copy.

## Typed settings and the web editor

Plugins can opt into validation and a generated settings form by declaring a
Pydantic model on `settings_model`. Give configurable fields defaults so a newly
installed plugin can operate before a user edits its settings.

```python
from pydantic import BaseModel, ConfigDict, Field
from bedrock_server_manager import PluginBase

class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = Field(default=True, description="Enable scheduled work.")
    interval_seconds: int = Field(default=30, ge=1, le=3600)

class MyPlugin(PluginBase):
    version = "1.0.0"
    settings_model = Settings
```

The **Plugins → Plugin Settings** page uses the model's JSON Schema for field
labels, help text, booleans, choices, numbers, and nested objects. Complex values
and plugins without a model use a JSON editor. The backend validates complete
settings objects before writing to the dedicated `plugin_settings` table.
Existing `get_plugin_setting` and `set_plugin_setting` methods remain supported;
reads include declared defaults, and writes also enforce the model. Validation
applies to administrative edits through global settings as well.

Schema changes take effect after plugin discovery/reload. Invalid existing values
must be corrected before the next write. Plugins decide when to reread settings;
configuration cached only in `on_load` requires a plugin reload. JSON Schema does
not replace backend validators, including custom Pydantic validators.
