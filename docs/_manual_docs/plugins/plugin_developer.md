# Developing Plugins

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

This guide will walk you through creating your own plugins to extend and customize the Bedrock Server Manager. The plugin system is designed to be simple yet powerful, allowing you to hook into various application events and use the core application's functions safely.

This guide assumes you have a basic understanding of Python programming. 

For a complete list of all available event hooks, see the [Availiable Hooks](./plugin_hooks.md).
For a complete list of all available event hooks, see the [Availiable APIs](./plugin_apis.md).

---

## 1. Getting Started: Your First Plugin

1.  **Locate the `plugins` directory:** Find the application's data directory. Inside, there will be a `plugins` folder.
2.  **Create a Python file:** Inside the `plugins` directory, create a new file (e.g., `my_first_plugin.py`). The filename (without the `.py`) will be used as your plugin's name.
3.  **Write the code:** In your new file, create a class that inherits from `PluginBase`.

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

4.  **Run the application:** Start the Bedrock Server Manager.
5.  **Enable your plugin:** Use the command `bedrock-server-manager plugin enable my_first_plugin` to activate it. You should see your "Hello from MyFirstPlugin!" message in the logs on the next startup.

## 2. The `PluginBase` Class

Every plugin **must** inherit from `bedrock_server_manager.PluginBase`. When your plugin is initialized, you are provided with three essential attributes:

*   `self.name` (str): The name of your plugin, derived from its filename.
*   `self.logger` (logging.Logger): A pre-configured Python logger. **Always use this for logging.**
*   `self.api` (PluginAPI): Your gateway to interacting with the main application.

```{important}
**Important Plugin Class Requirements:**

*   **`version` Attribute (Mandatory):** Your plugin class **must** define a class-level attribute named `version` as a string (e.g., `version = "1.0.0"`). Plugins without a valid `version` attribute will not be loaded.
*   **Description (from Docstring):** The description for your plugin is automatically extracted from the main docstring of your plugin class.
```

## 3. Understanding Event Hooks

Event hooks are methods from `PluginBase` that you can override. The Plugin Manager calls these methods when the corresponding event occurs.

*   **`before_*` events:** Called *before* an action is attempted.
*   **`after_*` events:** Called *after* an action has been attempted. They are always passed a `result` dictionary that you can inspect to see if the action succeeded or failed.

## 4. Custom Plugin Events (Inter-Plugin Communication)

Plugins can define, send, and listen to their own custom events for complex interactions.

*   **Sending Events:** Use `self.api.send_event("myplugin:custom_action", arg1, kwarg1="value")`.
*   **Listening for Events:** Use `self.api.listen_for_event("some:event", self.my_callback)` in your plugin's `on_load` method.
*   **Callback Arguments:** Your callback function will receive any `*args` and `**kwargs` from the sender.

### Example: "I'm Home" Automation (Triggered via HTTP API)

An external system can trigger a plugin to start a server by sending a `POST` request to `/api/plugins/trigger_event` with a JSON body. The corresponding plugin would listen for this event:

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

## 5. Best Practices

```{tip}
*   **Always use `self.logger`:** Do not use `print()`. The provided logger is integrated with the application's logging system.
*   **Handle exceptions:** Wrap API calls in `try...except` blocks to handle potential failures gracefully.
*   **Check the `result` dictionary:** After an `after_*` event, inspect the `result['status']` to confirm the outcome.
*   **Avoid blocking operations:** Long-running tasks in your event handlers can freeze the application. Offload them to separate threads if necessary.
*   **Use the API for operations:** Do not directly manipulate server files or directories. Use the provided `self.api` functions to ensure thread-safety and consistency.
```