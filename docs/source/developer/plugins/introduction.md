# Developing Plugins

```{image} https://raw.githubusercontent.com/DMedina559/bsm-frontend/main/frontend/public/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

This guide will walk you through creating your own plugins to extend and customize the Bedrock Server Manager. The plugin system is designed to be simple yet powerful, allowing you to hook into various application events and use the core application's functions safely.

This guide assumes you have a basic understanding of Python programming.

For a complete list of all available event, see the [Available Events](../../plugins/plugin_events.rst).
For a complete list of all available APIs, see the [Available APIs](../../plugins/plugin_apis.md).

---

## 1. Getting Started: Your First Plugin

1.  **Locate a `plugins` directory:**
    *   **User Plugins:** Find the application's data directory (typically `~/.bedrock-server-manager/` or where `BSM_DATA_DIR` points). Inside, there will be a `plugins` folder. This is for your custom plugins.
    *   **Default Plugins:** The application also ships with default plugins located within its installation source at `src/bedrock_server_manager/plugins/default/`. While you can look here for examples, you should place your custom plugins in the user plugins directory.
    *   **Root `plugins/` folder (for development/examples):** The main repository also contains a `plugins/` folder in its root. This is primarily for development-time examples and testing of the plugin system itself. For user-created plugins meant for regular use, the user plugins directory is preferred.
2.  **Choose your plugin structure:** Plugins can be single Python files or complete Python packages (directories). This will be detailed in the next section.
3.  **Write the code:** Create your plugin file(s) and define a class that inherits from `PluginBase`.

Here is the most basic "Hello World" plugin:

```python
# my_first_plugin.py
from bedrock_server_manager import PluginBase

class MyFirstPlugin(PluginBase):
    """
    This is an example description that will be saved in the database
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
5.  **Enable your plugin:** Navigate to the Web UI to activate it. You should see your "Hello from MyFirstPlugin!" message in the logs on the next startup or plugins reload.

---

## 2. Plugin Structures: Single File vs. Package

Bedrock Server Manager supports two primary ways to structure your plugin:

### 2.1. Single-File Plugin

This is the simplest structure, suitable for smaller plugins.

*   Create a Python file (e.g., `my_simple_plugin.py`) directly in one of the plugin search paths (e.g., your user `plugins` directory).
*   The filename (without the `.py` extension, so `my_simple_plugin` in this case) becomes the internal name of your plugin.
*   Your `PluginBase` subclass must be defined within this file.

This is the structure used in the "Hello World" example above.

### 2.2. Package-Based Plugin (Directory)

For more complex plugins that might include multiple Python modules, templates, static files, or other resources, structuring your plugin as a Python package (a directory) is recommended.

*   Create a directory in one of the plugin search paths (e.g., `plugins/my_packaged_plugin/`).
*   The name of this directory (`my_packaged_plugin`) becomes the internal name of your plugin.
*   Inside this directory, you **must** have an `__init__.py` file.
*   The main `PluginBase` subclass for your plugin should be defined (or imported and made available) in this `__init__.py` file.

**Example Directory Structure for a Packaged Plugin:**

```
plugins/
└── my_packaged_plugin/       # Plugin Name: my_packaged_plugin
    ├── __init__.py           # Main plugin file, contains MyPluginClass(PluginBase)
    └── internal_logic.py     # Optional: other Python modules for your plugin
```


## 2.3. Plugin Metadata Attributes

To help the Plugin Manager identify and display your plugin correctly, your `PluginBase` subclass should define several metadata attributes:

*   **`version`** (str) - *Required*. Used for versioning and updates.
*   **`name`** (str) - Optional. The display name of the plugin (defaults to the module's file name).
*   **`description`** (str) - Optional. A short sentence describing what your plugin does.
*   **`author`** (str) - Optional. The creator of the plugin.
*   **`dependencies`** (List[str]) - Optional. A list of plugin names that **must** load before this one.
*   **`optional_dependencies`** (List[str]) - Optional. Plugins to load first *if* they are present.

```python
from bedrock_server_manager import PluginBase

class MyAwesomePlugin(PluginBase):
    name = "My Awesome Automation Plugin"
    version = "1.0.0"
    author = "Jane Doe"
    description = "Automatically performs server backups and chat translations."
    dependencies = ["core_backup_plugin"]

    def on_load(self):
        self.logger.info(f"{self.name} v{self.version} by {self.author} loaded!")
```



This package structure allows for better organization. Python's standard import mechanisms (e.g., `from . import internal_logic`) will work within your plugin package.

---

## 3. The `PluginBase` Class

Every plugin **must** inherit from `bedrock_server_manager.PluginBase` (typically imported as `from bedrock_server_manager import PluginBase`). When your plugin is initialized, you are provided with three essential attributes:

*   `self.name` (str): The name of your plugin, derived from its filename.
*   `self.logger` (logging.Logger): A pre-configured Python logger. **Always use this for logging.**
*   `self.api` (AppAPI): Your gateway to interacting with the main application. It dynamically exposes core application APIs to plugins safely and with robust type hints available in most modern IDEs.

```{important}
**Important Plugin Class Requirements:**

*   **`version` Attribute (Mandatory):** Your plugin class **must** define a class-level attribute named `version` as a string (e.g., `version = "1.0.0"`). Plugins without a valid `version` attribute will not be loaded.
*   **Description (from Docstring):** The description for your plugin is automatically extracted from the main docstring of your plugin class.
```

## 3. Understanding Event Hooks

Event hooks are methods from `PluginBase` that you can override. The Plugin Manager calls these methods when the corresponding event occurs.

*   **`before_*` events:** Called *before* an action is attempted.
*   **`after_*` events:** Called *after* an action has been attempted. They are always passed a `result` dictionary that you can inspect to see if the action succeeded or failed.

### Asynchronous Event Hooks (New in 3.x)

To prevent plugins from blocking the main event loop (e.g., during long network requests or heavy I/O), BSM supports fully asynchronous event hooks.

You can define any of your event handlers as an `async def` instead of a standard synchronous `def`. The plugin manager will detect this and safely `await` your hook without freezing the rest of the application!

```python
import asyncio
from bedrock_server_manager import PluginBase

class MyAsyncPlugin(PluginBase):
    version = "1.1.0"

    async def before_start_server(self, server_name: str, **kwargs):
        """This hook will be awaited by the core application asynchronously!"""
        self.logger.info(f"Preparing to start {server_name} in 3 seconds...")

        # We can perform non-blocking waits, HTTP requests, or file I/O here
        await asyncio.sleep(3)

        self.logger.info(f"Done waiting. Let the server start!")
```

## 4. Advanced Topics

The plugin system offers many advanced features for deep integration:

*   **[Custom Events & Interception](./custom_events.md):** Learn how to send inter-plugin messages, trigger actions externally, and intercept/cancel core application operations before they happen.
*   **[Plugin Settings & Storage](./settings.md):** Discover how to persistently save and load configurations specific to your plugin within the application's database.
*   **[Custom FastAPI Endpoints](./fastapi_endpoints.md):** Extend the web server itself by registering your own web routes, APIs, and Native JSON UI pages.
*   **[Background Task Loops](./task_manager.md):** Use the `@task_loop` decorator to easily schedule asynchronous or synchronous repeating background jobs without blocking the main event loop.

## 5. Best Practices

```{tip}
*   **Always use `self.logger`:** Do not use `print()`. The provided logger is integrated with the application's logging system.
*   **Handle exceptions:** Wrap API calls in `try...except` blocks to handle potential failures gracefully.
*   **Check the `result` dictionary:** After an `after_*` event, inspect the `result['status']` to confirm the outcome.
*   **Avoid blocking operations:** Long-running tasks in your event handlers or FastAPI endpoints can freeze the application. Use the [Task Manager](./task_manager.md) to offload them to background threads.
*   **Use the API for operations:** Do not directly manipulate server files or directories. Use the provided `self.api` functions to ensure thread-safety and consistency.
```
