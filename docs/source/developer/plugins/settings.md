# Plugin Settings and Storage

## Managing Configuration

Plugins often need to store configuration data persistently.

### 1. Isolated Plugin Settings

Bedrock Server Manager provides built-in methods on `PluginBase` to safely read and write your plugin's configuration to the database without conflicting with other plugins or core settings. This data is stored globally for your plugin.

*   **Saving Data:** `self.set_plugin_setting(key="my_setting", value="my_value")`
*   **Loading Data:** `self.get_plugin_setting(key="my_setting", default="default_value")`

```python
from bedrock_server_manager import app_event, PluginBase

class MyConfigurablePlugin(PluginBase):
    version = "1.0.0"

    @app_event("on_load")
    def on_load(self):
        # Load existing settings or set defaults
        self.plugin_config = self.get_plugin_setting("config", default={"enable_feature_x": True})

        if "api_key" not in self.plugin_config:
            self.logger.info("Initializing defaults.")
            self.plugin_config["api_key"] = "YOUR_KEY_HERE"

            # Save the updated configuration
            self.set_plugin_setting("config", self.plugin_config)

        self.logger.info(f"Loaded config: {self.plugin_config}")
```

### 2. Custom Global Application Settings

If you need to store global settings outside of your plugin's isolated namespace, you can use the custom global setting API. These are stored in the database under the `custom.` namespace.

*   **Saving Data:** `self.api.set_custom_global_setting(key="my_global_key", value="my_value")`
*   **Loading Data:** `self.api.get_global_setting(key="custom.my_global_key")`

### 3. Server-Specific Custom Settings

You can also store custom JSON settings that apply only to a specific Minecraft server. This data is saved directly in that server's `[server_name]_config.json` file inside the `custom` section.

*   **Saving Server Data:** `self.api.set_server_custom_value(server_name="survival_world", key="some_key", value="some_value")`
*   **Loading Server Data:** `self.api.get_server_setting(server_name="survival_world", key="custom.some_key")`
