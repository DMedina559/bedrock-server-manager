# Bedrock Server Manager: Plugin API

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

This guide will walk you through creating your own plugins to extend and customize the Bedrock Server Manager. The plugin system is designed to be simple yet powerful, allowing you to hook into various application events and use the core application's functions safely.

This guide assumes you have a basic understanding of Python programming.

---

## 1. Getting Started: Your First Plugin

Creating a plugin is straightforward:

1.  **Locate the `plugins` directory:** Find the application's data directory. Inside, there will be a `plugins` folder. If it doesn't exist, the application will create it on first run.
2.  **Create a Python file:** Inside the `plugins` directory, create a new file (e.g., `my_first_plugin.py`). The filename (without the `.py`) will be used as your plugin's name.
3.  **Write the code:** In your new file, create a class that inherits from `PluginBase` and implement the event hooks you're interested in.

Here is the most basic "Hello World" plugin:

```python
# my_first_plugin.py
from bedrock_server_manager import PluginBase

class MyFirstPlugin(PluginBase):
    """
    This is an example description that will be saved in plugins.json
    """
    version = "1.0.0"  # Mandatory version attribute

    def on_load(self):
        """This event is called when the plugin is loaded by the manager."""
        self.logger.info("Hello from MyFirstPlugin!")

    def after_server_start(self, server_name: str, result: dict):
        """This event is called after a server has started."""
        if result.get("status") == "success":
            self.logger.info(f"Server '{server_name}' has started successfully!")
```

4.  **Run the application:** Start the Bedrock Server Manager. You should see your "Hello from MyFirstPlugin!" message in the logs.
5.  **Enable your plugin:** Use the command `bedrock-server-manager plugin enable my_first_plugin` to activate it. (See below for more details).

## 2. Managing Plugins

The Bedrock Server Manager allows users to control which plugins are active through a `plugins.json` configuration file and new CLI commands.

### `plugins.json` Configuration File

*   **Location:** This file is located in your application's configuration directory (typically `~/.bedrock-server-manager/.config/plugins.json`).
*   **Functionality:** It stores a JSON object where keys are plugin names (derived from their filenames) and values are booleans (`true` to enable, `false` to disable).
*   **Discovery:** When the application starts, it scans the plugin directories. Any new `.py` files found will be added to `plugins.json`.
*   **Default State for New Plugins:**
    *   **Standard Plugins:** By default, newly discovered user-added plugins are added to `plugins.json` as `disabled` (`false`).
    *   **Default Enabled Plugins:** A predefined list of essential built-in plugins are automatically enabled (`true`) by default. You can still disable them manually. The current list includes:
        *   `server_lifecycle_notifications`
        *   `world_operation_notifications`
        *   `auto_reload_config`
        *   `update_before_start`

### CLI Commands for Plugin Management

You can easily manage which plugins are active using the `bedrock-server-manager plugin` command-line interface:

*   **`bedrock-server-manager plugin list`**
    *   Displays all discovered plugins and their current status (Enabled/Disabled).
    *   Example:
        ```
        $ bedrock-server-manager plugin list
        Fetching plugin statuses...
        Plugin Statuses:
        Plugin Name                         | Status   | Version |
        ------------------------------------|----------|---------|
        server_lifecycle__notifications     | Enabled  | 1.0.0   |
        my_custom_plugin                    | Disabled | 1.4.5   |
        ```

*   **`bedrock-server-manager plugin enable <plugin_name>`**
    *   Enables the specified plugin.
    *   Example: `bedrock-server-manager plugin enable MyCustomPlugin`

*   **`bedrock-server-manager plugin disable <plugin_name>`**
    *   Disables the specified plugin.
    *   Example: `bedrock-server-manager plugin disable server_lifecycle_notifications`

Changes made via these commands are immediately saved to `plugins.json` and will be applied on the next application start or plugin reload.

## 3. The `PluginBase` Class

Every plugin **must** inherit from `bedrock_server_manager.PluginBase`. When your plugin is initialized, you are provided with three essential attributes:

*   `self.name` (str): The name of your plugin, derived from its filename.
*   `self.logger` (logging.Logger): A pre-configured Python logger. **Always use this for logging.**
*   `self.api` (PluginAPI): Your gateway to interacting with the main application.

```{important}
**Important Plugin Class Requirements:**

*   **`version` Attribute (Mandatory):** Your plugin class **must** define a class-level attribute named `version` as a string (e.g., `version = "1.0.0"`). Plugins without a valid `version` attribute will not be loaded.
*   **Description (from Docstring):** The description for your plugin is automatically extracted from the main docstring of your plugin class.
```

```python
class MyAwesomePlugin(PluginBase):
    """
    This is the description of MyAwesomePlugin.
    It will be saved in the plugins.json.
    """
    version = "1.2.3" # Mandatory

    def on_load(self):
        self.logger.info("MyAwesomePlugin loaded!")
```

## 4. Understanding Event Hooks

Event hooks are methods from `PluginBase` that you can override. The Plugin Manager calls these methods when the corresponding event occurs.

*   **`before_*` events:** Called *before* an action is attempted.
*   **`after_*` events:** Called *after* an action has been attempted. They are always passed a `result` dictionary that you can inspect to see if the action succeeded or failed.

## 5. Complete List of Event Hooks

Here are all the methods you can implement in your plugin class.

### Plugin Lifecycle Events
*   `on_load(self)`
    -   Called once when your plugin is successfully loaded by the Plugin Manager.
*   `on_unload(self)`
    -   Called once when the application is shutting down.

### Server Start/Stop Events
*   `before_server_start(self, server_name: str, mode: str)`
    -   Called just before a server start is attempted.
*   `after_server_start(self, server_name: str, result: dict)`
    -   Called just after a server start has been attempted.
*   `before_server_stop(self, server_name: str)`
    -   Called just before a server stop is attempted.
*   `after_server_stop(self, server_name: str, result: dict)`
    -   Called just after a server stop has been attempted.

### Server Command Events
*   `before_command_send(self, server_name: str, command: str)`
    -   Called before a command is sent to a server.
*   `after_command_send(self, server_name: str, command: str, result: dict)`
    -   Called after a command has been sent to a server.

### Backup & Restore Events
*   `before_backup(self, server_name: str, backup_type: str, **kwargs)`
    -   Called before a backup operation begins.
*   `after_backup(self, server_name: str, backup_type: str, result: dict, **kwargs)`
    -   Called after a backup operation completes.
*   `before_restore(self, server_name: str, restore_type: str, **kwargs)`
    -   Called before a restore operation begins.
*   `after_restore(self, server_name: str, restore_type: str, result: dict, **kwargs)`
    -   Called after a restore operation completes.
*   `before_prune_backups(self, server_name: str)`
    -   Called before old backups are pruned for a server.
*   `after_prune_backups(self, server_name: str, result: dict)`
    -   Called after an attempt to prune old backups completes.

### World Management Events
*   `before_world_export(self, server_name: str, export_dir: str)`
    -   Called before a server's world is exported.
*   `after_world_export(self, server_name: str, result: dict)`
    -   Called after an attempt to export a world completes.
*   `before_world_import(self, server_name: str, file_path: str)`
    -   Called before a `.mcworld` file is imported to a server.
*   `after_world_import(self, server_name: str, result: dict)`
    -   Called after an attempt to import a world completes.
*   `before_world_reset(self, server_name: str)`
    -   Called before a server's active world directory is deleted.
*   `after_world_reset(self, server_name: str, result: dict)`
    -   Called after an attempt to reset a world completes.

### Addon Management Events
*   `before_addon_import(self, server_name: str, addon_file_path: str)`
    -   Called before an addon file is imported to a server.
*   `after_addon_import(self, server_name: str, result: dict)`
    -   Called after an attempt to import an addon completes.

### Server Configuration Events
*   `before_allowlist_change(self, server_name: str, players_to_add: list, players_to_remove: list)`
    -   Called before a server's `allowlist.json` is modified.
*   `after_allowlist_change(self, server_name: str, result: dict)`
    -   Called after an attempt to modify the allowlist completes.
*   `before_permission_change(self, server_name: str, xuid: str, permission: str)`
    -   Called before a player's permission level is changed.
*   `after_permission_change(self, server_name: str, xuid: str, result: dict)`
    -   Called after an attempt to change a player's permission completes.
*   `before_properties_change(self, server_name: str, properties: dict)`
    -   Called before `server.properties` is modified.
*   `after_properties_change(self, server_name: str, result: dict)`
    -   Called after an attempt to modify `server.properties` completes.

### Server Installation & Update Events
*   `before_server_install(self, server_name: str, target_version: str)`
    -   Called before a new server installation begins.
*   `after_server_install(self, server_name: str, result: dict)`
    -   Called after a new server installation attempt completes.
*   `before_server_update(self, server_name: str, target_version: str)`
    -   Called before an existing server is updated.
*   `after_server_update(self, server_name: str, result: dict)`
    -   Called after a server update attempt completes.

### Player Database Events
*   `before_players_add(self, players_data: list)`
    -   Called before players are manually added to the central player DB.
*   `after_players_add(self, result: dict)`
    -   Called after an attempt to manually add players completes.
*   `before_player_db_scan(self)`
    -   Called before a scan of all server logs for new players begins.
*   `after_player_db_scan(self, result: dict)`
    -   Called after a scan of server logs for players has completed.

### System & Application Events
*   `before_service_change(self, server_name: str, action: str)`
    -   Called before a system service (e.g., systemd) is changed.
*   `after_service_change(self, server_name: str, action: str, result: dict)`
    -   Called after an attempt to change a system service completes.
*   `before_autoupdate_change(self, server_name: str, new_value: bool)`
    -   Called before a server's autoupdate setting is changed.
*   `after_autoupdate_change(self, server_name: str, result: dict)`
    -   Called after an attempt to change the autoupdate setting completes.
*   `before_prune_download_cache(self, download_dir: str, keep_count: int)`
    -   Called before the global download cache is pruned.
*   `after_prune_download_cache(self, result: dict)`
    -   Called after an attempt to prune the download cache completes.
*   `on_manager_startup(self)`
    -   Called once when the Plugin Manager finishes loading all plugins and the API is ready.

### Web Server Events
*   `before_web_server_start(self, mode: str)`
    -   Called just before the web server start is attempted.
*   `after_web_server_start(self, result: dict)`
    -   Called just after a web server start has been attempted.
*   `before_web_server_stop(self)`
    -   Called just before a web server stop is attempted.
*   `after_web_server_stop(self, result: dict)`
    -   Called just after a web server stop has been attempted.

## 6. Custom Plugin Events (Inter-Plugin Communication)

Plugins can define, send, and listen to their own custom events for complex interactions. This allows communication between plugins or between an external trigger (like an HTTP API call) and a plugin.

**Core Concepts:**

*   **Event Names:** Use namespaced strings (e.g., `"myplugin:custom_action"`).
*   **Sending Events:** Use `self.api.send_event(...)` from within a plugin, or trigger externally via the `POST /api/plugins/trigger_event` API endpoint or `bsm plugin trigger_event` CLI command.
*   **Listening for Events:** Use `self.api.listen_for_event("some:event", self.my_callback)` in your plugin's `on_load` method.
*   **Callback Arguments:** Your callback function will receive any `*args` and `**kwargs` from the sender, plus a special `_triggering_plugin` keyword argument indicating the event source.

### Example: "I'm Home" Automation (Triggered via HTTP API)

An external system can trigger a plugin to start a server by sending a `POST` request to `/api/plugins/trigger_event` with this body:

```json
{
    "event_name": "automation:user_arrived_home",
    "payload": {
        "user_id": "user123",
        "location_name": "Home"
    }
}
```

The corresponding plugin would listen for this event:

```python
# home_automation_starter_plugin.py
from bedrock_server_manager import PluginBase

TARGET_SERVER_NAME = "main_survival"

class HomeAutomationStarterPlugin(PluginBase):
    version = "1.0.0"

    def on_load(self):
        self.logger.info(f"Listening for 'automation:user_arrived_home' to start '{TARGET_SERVER_NAME}'.")
        self.api.listen_for_event("automation:user_arrived_home", self.handle_user_arrival)

    def handle_user_arrival(self, **kwargs):
        user_id = kwargs.get('user_id', 'UnknownUser')
        self.logger.info(f"Received arrival event for user '{user_id}'.")
        
        status = self.api.get_server_running_status(server_name=TARGET_SERVER_NAME)
        if status.get("running"):
             self.logger.info(f"Server '{TARGET_SERVER_NAME}' is already running.")
             return

        self.api.start_server(server_name=TARGET_SERVER_NAME, mode="detached")
```

## 7. Available API Functions

> _This section was auto-generated by the `api_docs_generator` plugin on 2025-07-03 00:48:07 UTC._
> _Application Version: 3.5.0a1_

---
This lists all functions available to plugins via the `self.api` object.

## `add_players_manually_api`
```python
self.api.add_players_manually_api(player_strings: List[str])
```
**Description:** Adds or updates player data in the central players.json file.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `player_strings` | `List[str]` | `REQUIRED` |

---

## `add_players_to_allowlist_api`
```python
self.api.add_players_to_allowlist_api(server_name: str, new_players_data: List[Dict[str, Any]])
```
**Description:** Adds new players to the allowlist for a specific server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `new_players_data` | `List[Dict[str, Any]]` | `REQUIRED` |

---

## `backup_all`
```python
self.api.backup_all(server_name: str, stop_start_server: bool = True)
```
**Description:** Performs a full backup of the server's world and configuration files.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `stop_start_server` | `bool` | `True` |

---

## `backup_config_file`
```python
self.api.backup_config_file(server_name: str, file_to_backup: str, stop_start_server: bool = True)
```
**Description:** Creates a backup of a specific server configuration file.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `file_to_backup` | `str` | `REQUIRED` |
| `stop_start_server` | `bool` | `True` |

---

## `backup_world`
```python
self.api.backup_world(server_name: str, stop_start_server: bool = True)
```
**Description:** Creates a backup of the server's world directory.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `stop_start_server` | `bool` | `True` |

---

## `configure_player_permission`
```python
self.api.configure_player_permission(server_name: str, xuid: str, player_name: Optional[str], permission: str)
```
**Description:** Sets a player's permission level in permissions.json.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `xuid` | `str` | `REQUIRED` |
| `player_name` | `Optional[str]` | `REQUIRED` |
| `permission` | `str` | `REQUIRED` |

---

## `get_all_known_players_api`
```python
self.api.get_all_known_players_api()
```
**Description:** Retrieves all player data from the central players.json file.


---

## `get_all_server_settings`
```python
self.api.get_all_server_settings(server_name: str)
```
**Description:** Reads the entire JSON configuration for a specific server from its

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `get_all_servers_data`
```python
self.api.get_all_servers_data()
```
**Description:** Retrieves status and version for all detected servers.


---

## `get_application_info_api`
```python
self.api.get_application_info_api()
```
**Description:** Retrieves general information about the application.


---

## `get_bedrock_process_info`
```python
self.api.get_bedrock_process_info(server_name: str)
```
**Description:** Retrieves resource usage for a running Bedrock server process.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `get_plugin_statuses`
```python
self.api.get_plugin_statuses()
```
**Description:** Retrieves the statuses and metadata of all discovered plugins.


---

## `get_server_allowlist_api`
```python
self.api.get_server_allowlist_api(server_name: str)
```
**Description:** Retrieves the allowlist for a specific server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `get_server_config_status`
```python
self.api.get_server_config_status(server_name: str)
```
**Description:** Gets the status from the server's configuration file.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `get_server_installed_version`
```python
self.api.get_server_installed_version(server_name: str)
```
**Description:** Gets the installed version from the server's configuration file.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `get_server_permissions_api`
```python
self.api.get_server_permissions_api(server_name: str)
```
**Description:** Retrieves processed permissions data for a server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `get_server_properties_api`
```python
self.api.get_server_properties_api(server_name: str)
```
**Description:** Reads and returns the `server.properties` file for a server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `get_server_running_status`
```python
self.api.get_server_running_status(server_name: str)
```
**Description:** Checks if the server process is currently running.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `get_server_setting`
```python
self.api.get_server_setting(server_name: str, key: str)
```
**Description:** Reads any value from a server's specific JSON configuration file

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `key` | `str` | `REQUIRED` |

---

## `get_system_and_app_info`
```python
self.api.get_system_and_app_info()
```
**Description:** Retrieves basic system and application information.


---

## `get_web_server_status`
```python
self.api.get_web_server_status()
```
**Description:** Checks the status of the web server process.


---

## `import_addon`
```python
self.api.import_addon(server_name: str, addon_file_path: str, stop_start_server: bool = True, restart_only_on_success: bool = True)
```
**Description:** Installs an addon to a specified Bedrock server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `addon_file_path` | `str` | `REQUIRED` |
| `stop_start_server` | `bool` | `True` |
| `restart_only_on_success` | `bool` | `True` |

---

## `install_new_server`
```python
self.api.install_new_server(server_name: str, target_version: str = 'LATEST')
```
**Description:** Installs a new Bedrock server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `target_version` | `str` | `'LATEST'` |

---

## `list_available_addons_api`
```python
self.api.list_available_addons_api()
```
**Description:** Lists available .mcaddon and .mcpack files from the content directory.


---

## `list_available_worlds_api`
```python
self.api.list_available_worlds_api()
```
**Description:** Lists available .mcworld files from the content directory.


---

## `list_backup_files`
```python
self.api.list_backup_files(server_name: str, backup_type: str)
```
**Description:** Lists available backup files for a given server and type.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `backup_type` | `str` | `REQUIRED` |

---

## `modify_server_properties`
```python
self.api.modify_server_properties(server_name: str, properties_to_update: Dict[str, str], restart_after_modify: bool = True)
```
**Description:** Modifies one or more properties in `server.properties`.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `properties_to_update` | `Dict[str, str]` | `REQUIRED` |
| `restart_after_modify` | `bool` | `True` |

---

## `prune_download_cache`
```python
self.api.prune_download_cache(download_dir: str, keep_count: Optional[int] = None)
```
**Description:** Prunes old downloaded server archives (.zip) in a directory.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `download_dir` | `str` | `REQUIRED` |
| `keep_count` | `Optional[int]` | `None` |

---

## `prune_old_backups`
```python
self.api.prune_old_backups(server_name: str)
```
**Description:** Prunes old backups for a server based on retention settings.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `remove_players_from_allowlist`
```python
self.api.remove_players_from_allowlist(server_name: str, player_names: List[str])
```
**Description:** Removes one or more players from the server's allowlist by name.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `player_names` | `List[str]` | `REQUIRED` |

---

## `restart_server`
```python
self.api.restart_server(server_name: str, send_message: bool = True)
```
**Description:** Restarts the specified Bedrock server by orchestrating stop and start.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `send_message` | `bool` | `True` |

---

## `restore_all`
```python
self.api.restore_all(server_name: str, stop_start_server: bool = True)
```
**Description:** Restores the server from the latest available backups.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `stop_start_server` | `bool` | `True` |

---

## `restore_config_file`
```python
self.api.restore_config_file(server_name: str, backup_file_path: str, stop_start_server: bool = True)
```
**Description:** Restores a specific config file from a backup.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `backup_file_path` | `str` | `REQUIRED` |
| `stop_start_server` | `bool` | `True` |

---

## `restore_world`
```python
self.api.restore_world(server_name: str, backup_file_path: str, stop_start_server: bool = True)
```
**Description:** Restores a server's world from a specific backup file.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `backup_file_path` | `str` | `REQUIRED` |
| `stop_start_server` | `bool` | `True` |

---

## `scan_and_update_player_db_api`
```python
self.api.scan_and_update_player_db_api()
```
**Description:** Scans all server logs to discover and save player data.


---

## `send_command`
```python
self.api.send_command(server_name: str, command: str)
```
**Description:** Sends a command to a running Bedrock server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `command` | `str` | `REQUIRED` |

---

## `set_server_custom_value`
```python
self.api.set_server_custom_value(server_name: str, key: str, value: Any)
```
**Description:** Writes a key-value pair to the 'custom' section of a server's specific

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `key` | `str` | `REQUIRED` |
| `value` | `Any` | `REQUIRED` |

---

## `start_server`
```python
self.api.start_server(server_name: str, mode: str = 'direct')
```
**Description:** Starts the specified Bedrock server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `mode` | `str` | `'direct'` |

---

## `stop_server`
```python
self.api.stop_server(server_name: str)
```
**Description:** Stops the specified Bedrock server.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `trigger_external_plugin_event_api`
```python
self.api.trigger_external_plugin_event_api(event_name: str, payload: Dict[str, Any] = None)
```
**Description:** Allows an external source (like a web route or CLI) to trigger a custom plugin event.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `event_name` | `str` | `REQUIRED` |
| `payload` | `Dict[str, Any]` | `None` |

---

## `update_server`
```python
self.api.update_server(server_name: str, send_message: bool = True)
```
**Description:** Updates an existing server to its configured target version.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |
| `send_message` | `bool` | `True` |

---

## `validate_server_exist`
```python
self.api.validate_server_exist(server_name: str)
```
**Description:** Validates if a server is correctly installed.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `validate_server_name_format`
```python
self.api.validate_server_name_format(server_name: str)
```
**Description:** Validates the format of a potential server name.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `server_name` | `str` | `REQUIRED` |

---

## `validate_server_property_value`
```python
self.api.validate_server_property_value(property_name: str, value: str)
```
**Description:** Validates a single server property value based on known rules.

**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `property_name` | `str` | `REQUIRED` |
| `value` | `str` | `REQUIRED` |


## 8. Best Practices

```{tip}
*   **Always use `self.logger`:** Do not use `print()`. The provided logger is integrated with the application's logging system.
*   **Handle exceptions:** Wrap API calls in `try...except` blocks to handle potential failures gracefully without crashing your plugin.
*   **Check the `result` dictionary:** After calling an API function, inspect the returned dictionary (e.g., `result['status']`) to confirm the outcome.
*   **Avoid blocking operations:** Long-running tasks in your event handlers can freeze the application. Offload them to separate threads if necessary.
*   **Use the API for operations:** Do not directly manipulate server files or directories. Use the provided `self.api` functions to ensure thread-safety and consistency.
```