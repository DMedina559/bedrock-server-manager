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


### Server references

Use `ExistingServerName` for fields that refer to installed servers:

```python
from pydantic import BaseModel, ConfigDict, Field
from bedrock_server_manager import ExistingServerName, PluginBase

class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    servers: list[ExistingServerName] = Field(default_factory=list)

class MyPlugin(PluginBase):
    settings_model = Settings
```

The settings service supplies live validation context when saving settings, and
adds current server choices to the settings schema returned to the web UI.
References must name a registered server with an executable and
`server.properties`. A static enum is unnecessary. Standalone model validation
checks the name format; pass `context={"server_names": names}` to validate
existence outside the settings service.

Plugins can request current valid names without sampling server processes:

```python
result = await self.api.server.get_valid_server_names(request={})
names = result.server_names
```

Saved references can become unavailable after server deletion or file damage.
Recheck existence before performing operations; ordinary app server lookup
validates the installation again. Auto Backup On Start uses an empty server
selection to mean all servers, and reads its selection for every start event.

## Plugin-owned configuration files

Use `await self.api.runtime.write_plugin_file("settings.json", value)` to atomically write JSON inside this plugin's configuration directory. Read it with `await self.api.runtime.read_plugin_file("settings.json")`.

Paths are relative to `<config_dir>/config/plugins/<plugin-id>/`. Traversal and symlink escapes are rejected, ownership is injected by the runtime, and capabilities from an unloaded plugin are revoked. Use the existing plugin settings API for ordinary structured settings; these file methods are for plugin-owned JSON files.

The application does not expose its credentials directory through this capability. In-process Python plugins are trusted code with the host process's operating-system permissions; scoped APIs are not an OS sandbox.


## Global and server settings models

Declare optional models alongside the existing `settings_model`:

```python
from pydantic import BaseModel, ConfigDict, Field
from bedrock_server_manager import PluginBase

class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = True
    retries: int = Field(default=3, ge=0, le=10)

class MyPlugin(PluginBase):
    version = "1.0.0"
    settings_model = Policy
    global_settings_model = Policy
    server_settings_model = Policy
```

Each model is independent. Global and server values live in that scope's `custom.<plugin_name>` namespace. Plugin-local values retain their existing storage. Scoped declarations require a plugin identifier that is a single safe namespace segment. Core settings and other plugins' schemas cannot be redefined through these declarations.

```python
policy = await self.get_plugin_settings(scope="global")
await self.set_plugin_setting("retries", 4, scope="global")
await self.set_plugin_settings(
    {"enabled": True, "retries": 2},
    scope="server", server_name="survival",
)
```

Omitting scope continues to address plugin-local settings. Server scope requires an existing `server_name`; other scopes must omit it. A whole-namespace write is atomic, and field writes validate against the latest committed namespace so concurrent sibling changes are retained. Defaults are supplied on read without persisting them. Validators receive `server_names`, `server_name`, and `plugin_name` in their Pydantic context.

Ordinary global/server setting writes and server-settings restores validate changed registered namespaces at the storage transaction boundary, before database commit and state publication. Stored values remain when a plugin is disabled or removed; discovery retains models for installed disabled plugins, and refreshes registrations when plugins reload.

`GET /api/plugins/{plugin_name}/settings` and `PUT /api/plugins/{plugin_name}/settings` accept `scope` and optional `server_name` parameters and return the scope's model schema for the frontend editor.

## Scheduled task options and execution context

Register plugin tasks with `self.api.runtime.register_scheduled_task`:

```python
class TaskOptions(BaseModel):
    count: int = Field(default=1, ge=1, le=100)

self.api.runtime.register_scheduled_task(
    "my_plugin:cleanup", self.cleanup,
    options_model=TaskOptions,
    timeout_seconds=300,
    requires_server_lock=False,
    with_context=True,
)

async def cleanup(self, *, server_name, options, execution_context):
    key = execution_context["idempotency_key"]
    # Use key to recognize a repeated attempt before producing external effects.
```

All registration keywords are optional. Existing handlers continue receiving only
`server_name` and `options`. The default server lock remains enabled. Choose
`requires_server_lock=False` only when the task does not need exclusive server
access; operations called through the API still apply their own locks. Plugin task
timeouts default to 300 seconds and can be set from 1 through 86400 seconds.
Cancellation is cooperative; handlers must propagate cancellation and clean up in
`finally` blocks. Long built-in backups do not inherit this plugin timeout.

An options model validates saved options and validates again before execution.
The scheduler listing exposes its JSON Schema for clients. With context enabled,
the handler additionally receives a stable slot/idempotency key, attempt number,
and operation correlation ID. A manual run has its own slot. Execution is
at-least-once across a crash; database claims and completed-run reconciliation do
not replace idempotency for external effects. Disabled or unloaded plugin owners
cannot run registered handlers.
