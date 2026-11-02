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
result = await self.api.server.get_valid_names(request={})
names = result.server_names
```

Saved references can become unavailable after server deletion or file damage.
Recheck existence before performing operations; ordinary app server lookup
validates the installation again. Auto Backup On Start uses an empty server
selection to mean all servers, and reads its selection for every start event.

## Plugin-owned configuration and data files

When your plugin needs to store larger JSON documents, plain-text templates, binary exports, or multi-file datasets on disk rather than inside the SQLite settings table, use the scoped file capabilities on `self.api.runtime`:

| Method | Signature | Description |
|---|---|---|
| `write_plugin_file` | `await self.api.runtime.write_plugin_file(filename, value, *, scope="private", format="json") -> Path` | Atomically write a file inside the selected plugin data root and return its resolved `Path`. |
| `read_plugin_file` | `await self.api.runtime.read_plugin_file(filename, *, scope="private", format="json")` | Read and decode a file from the selected plugin data root. |
| `get_plugin_data_path` | `await self.api.runtime.get_plugin_data_path(filename="", *, scope="private") -> Path` | Resolve a validated directory (`filename=""`) or file path inside the selected plugin data root, creating parent directories as needed. |

### Storage scopes and directory roots

- **`scope="private"` (default):** Resolves under `<config_dir>/plugins/<plugin_name>/`. Each plugin gets its own isolated directory. On first access, if a legacy directory exists at `<config_dir>/config/plugins/<plugin_name>` and the new directory does not yet exist, BSM automatically migrates the legacy directory.
- **`scope="public"` or `scope="shared"`:** Both resolve under `<config_dir>/plugins/public/`. Any plugin can read and write files here to share artifacts, exports, or cross-plugin data, and directories inside `<config_dir>/plugins/public/` can also be mounted as static web assets via `static_mounts`.
- **Reserved directory names (`public`, `shared`, `private`):** Because `<config_dir>/plugins/public/` is reserved for shared storage, BSM reserves the names `public`, `shared`, and `private`. A plugin file or package using any of those names cannot be loaded or access private storage.

### Supported file formats (`format`)

- **`format="json"` (default):** `write_plugin_file` serializes JSON-compatible values (`dict`, `list`, `str`, `int`, `float`, `bool`, `None`) with 2-space indentation and rejects `NaN`/`Infinity`. `read_plugin_file` parses and returns the decoded Python value.
- **`format="text"`:** `write_plugin_file` requires a `str` and writes UTF-8 text; `read_plugin_file` decodes and returns a UTF-8 `str`.
- **`format="bytes"`:** `write_plugin_file` requires `bytes` or `bytearray`; `read_plugin_file` returns raw `bytes`.

```python
# 1. Write and read private JSON data
await self.api.runtime.write_plugin_file(
    "cache/state.json",
    {"last_sync": "2026-01-01T00:00:00Z", "items": [1, 2, 3]},
)
state = await self.api.runtime.read_plugin_file("cache/state.json")

# 2. Write a shared plain-text report to <config_dir>/plugins/public/reports/summary.txt
await self.api.runtime.write_plugin_file(
    "reports/summary.txt",
    "All servers healthy.\n",
    scope="public",
    format="text",
)

# 3. Resolve the plugin's private root directory to list or delete files
private_dir = await self.api.runtime.get_plugin_data_path(scope="private")
for path in private_dir.glob("cache/*.json"):
    path.unlink(missing_ok=True)
```

### Path validation, atomic writes, and restricted directories

- **Relative path validation (`safe_name`):** `filename` must be a relative POSIX path (1–1024 characters) using forward slashes (`/`). Absolute paths, backslashes (`\`), drive letters (`C:`), control characters, `.` or `..` traversal segments, and Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`) raise `ValueError`.
- **Symlink rejection:** Every path component from `<config_dir>/plugins` down to the target file is checked for symbolic links; symlinks anywhere in the chain are rejected (`ValueError: Plugin file path may not traverse symlinks`).
- **Atomic writes & permissions:** Writes use temporary sibling files and atomic replacement, applying `0o700` to directories and `0o600` to files on POSIX (and restricted owner DACLs on Windows).
- **Restricted `<config_dir>/credentials/` directory:** Application secrets (`jwt_secret.key`, `encryption_key.key`, `internal_service_token.key`) live in `<config_dir>/credentials/` and are never accessible through `read_plugin_file`, `write_plugin_file`, or `get_plugin_data_path`. Note that in-process Python plugins are trusted code running with the host process's OS permissions; scoped file APIs prevent accidental path bugs and traversal, not hostile OS-level access.
- **Generation binding:** Capabilities from an unloaded or reloaded plugin generation are revoked and raise `PluginCapabilityError`.

Use the typed plugin settings API (`settings_model`, `get_plugin_setting`, `set_plugin_setting`) for structured user-editable configuration, and reserve `read_plugin_file` / `write_plugin_file` / `get_plugin_data_path` for plugin-managed files and artifacts.


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

Each model is independent. Global and server values live in that scope's `custom.<plugin_name>` namespace. Plugin-local values retain their existing storage. Scoped declarations require a plugin identifier that is a single safe namespace segment: the plugin's module/package name must not start with `_`, contain `.`, or contain `__`, and cannot match a reserved setting namespace (`custom`, `server_info`, `settings_version`, or any core top-level key). Core settings and other plugins' schemas cannot be redefined through these declarations.

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

HTTP permissions follow the selected storage scope: plugin-local GET/PUT require
`plugins:read`/`plugins:manage`; global GET/PUT require `settings:read`/`settings:manage`;
server GET/PUT require `servers:read`/`servers:configure` on the selected server.
The ordinary global settings endpoint does not include the separate plugin-owned
table. Global/server custom fields remain part of their own setting scope.

For validating per-schedule task options with Pydantic models, see [Scheduled tasks in plugins](scheduled_tasks.md).
