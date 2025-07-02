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

(Abridged for brevity - see the provided prompt for the full, detailed list. The structure would be as follows:)

### Plugin Lifecycle Events
*   `on_load(self)`
*   `on_unload(self)`

### Server Start/Stop Events
*   `before_server_start(self, server_name: str, mode: str)`
*   `after_server_start(self, server_name: str, result: dict)`
*   `before_server_stop(self, server_name: str)`
*   `after_server_stop(self, server_name: str, result: dict)`

... and so on for all other event categories.

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

The following functions are available through `self.api`. All functions return a dictionary, typically with a `status` and `message` key.

### Server Management

*   `start_server(server_name: str, mode: str = "direct") -> dict`
*   `stop_server(server_name: str, mode: str = "direct") -> dict`
*   `send_command(server_name: str, command: str) -> dict`

### World Management

*   `export_world(server_name: str, ...) -> dict`
*   `import_world(server_name: str, file_path: str, ...) -> dict`
*   `reset_world(server_name: str) -> dict`

### Backup & Restore

*   `backup_all(server_name: str, ...) -> dict`
*   `restore_all(server_name: str, ...) -> dict`
*   `prune_old_backups(server_name: str) -> dict`

... and so on for all other API function categories.

## 8. Best Practices

```{tip}
*   **Always use `self.logger`:** Do not use `print()`. The provided logger is integrated with the application's logging system.
*   **Handle exceptions:** Wrap API calls in `try...except` blocks to handle potential failures gracefully without crashing your plugin.
*   **Check the `result` dictionary:** After calling an API function, inspect the returned dictionary (e.g., `result['status']`) to confirm the outcome.
*   **Avoid blocking operations:** Long-running tasks in your event handlers can freeze the application. Offload them to separate threads if necessary.
*   **Use the API for operations:** Do not directly manipulate server files or directories. Use the provided `self.api` functions to ensure thread-safety and consistency.
```