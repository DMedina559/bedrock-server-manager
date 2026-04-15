# Developing Plugins

```{image} https://raw.githubusercontent.com/DMedina559/bsm-frontend/main/frontend/public/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

This guide will walk you through creating your own plugins to extend and customize the Bedrock Server Manager. The plugin system is designed to be simple yet powerful, allowing you to hook into various application events and use the core application's functions safely.

This guide assumes you have a basic understanding of Python programming.

For a complete list of all available event hooks, see the [Plugin Base](./plugin_base.rst).
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

This package structure allows for better organization. Python's standard import mechanisms (e.g., `from . import internal_logic`) will work within your plugin package.

---

## 3. The `PluginBase` Class

Every plugin **must** inherit from `bedrock_server_manager.PluginBase` (typically imported as `from bedrock_server_manager import PluginBase`). When your plugin is initialized, you are provided with three essential attributes:

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

### Advanced Event Hooks (Interception)

You can use `before_*` hooks to intercept actions and potentially prevent them from happening or run prerequisites.

```python
class BackupBeforeStartPlugin(PluginBase):
    version = "1.0.0"

    def before_start_server(self, server_name: str, **kwargs):
        """Runs automatically before a server is started."""
        self.logger.info(f"Intercepted start request for {server_name}. Running quick backup...")

        # We can call another core API method synchronously
        result = self.api.backup_world(server_name=server_name)

        if result.get("status") == "success":
            self.logger.info("Backup completed. Allowing server to start.")
        else:
            self.logger.error("Backup failed! The server will still attempt to start, but check logs.")
```

## 5. Plugin Settings and Storage

Plugins often need to store configuration data persistently. Bedrock Server Manager provides methods to read and write to the global `bedrock-server-manager.db` file under a special `custom` section.

*   **Saving Data:** `self.api.set_custom_global_setting(key="my_plugin_key", value="my_value")`
*   **Loading Data:** `self.api.get_global_setting(key="custom.my_plugin_key")`

```python
class MyConfigurablePlugin(PluginBase):
    version = "1.0.0"

    def on_load(self):
        # Load existing settings or set defaults
        self.plugin_config = self.api.get_global_setting("custom.my_configurable_plugin")

        if not self.plugin_config:
            self.logger.info("No configuration found. Initializing defaults.")
            default_config = {"enable_feature_x": True, "api_key": "YOUR_KEY_HERE"}

            # Save the default configuration
            self.api.set_custom_global_setting("my_configurable_plugin", default_config)
            self.plugin_config = default_config

        self.logger.info(f"Loaded config: {self.plugin_config}")
```

## 6. Extending Functionality: Custom FastAPI Endpoints

Plugins can significantly extend Bedrock Server Manager by adding their own custom FastAPI web endpoints. This allows for deep integration and tailored functionality.

To enable this, your plugin class (derived from `PluginBase`) needs to override one or both of the following methods:

*   **`get_fastapi_routers(self) -> List[fastapi.APIRouter]`**:
    This method should return a list of FastAPI `APIRouter` instances that your plugin wants to add to the main web application.

The Plugin Manager will call these methods on your plugin instance after it's loaded. The collected commands and routers are then integrated into the main application.

### 6.1. Adding Custom FastAPI Endpoints (Web APIs and Pages)

To add web endpoints, define your FastAPI `APIRouter` instances and return them in a list from `get_fastapi_routers()`. These routers will be included in the main FastAPI application.

**Example:**

```python
# my_web_api_plugin.py
from bedrock_server_manager import PluginBase
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

# Attempt to import authentication dependency; provide a fallback for isolated testing/robustness
# There are three access roles admin, moderator, and user.

# - get_current_user: User, read only access APIs
# - get_moderator_user: Moderator, basic server management APIs, not including installs, updates, or content management
# - get_admin_user: Admin, full access to all APIs

try:
    from bedrock_server_manager.web import get_current_user
    HAS_AUTH_DEP = True
except ImportError:
    HAS_AUTH_DEP = False
    async def get_current_active_user(): return {"username": "anonymous_plugin_user"} # Dummy

# Create an APIRouter instance
plugin_web_router = APIRouter(
    prefix="/my_web_plugin",  # URL prefix for all routes in this router
    tags=["My Web Plugin"],   # Tag for OpenAPI documentation (e.g., /docs)
    dependencies=[Depends(get_current_user)] if HAS_AUTH_DEP else [] # Secure all routes
)

@plugin_web_router.get("/info")
async def get_plugin_web_info():
    """Returns some information via the plugin's web API."""
    return {"plugin_name": "My Web API Plugin", "message": "API is active!"}

@plugin_web_router.post("/submit_data")
async def submit_data_to_plugin(data: dict):
    """A sample POST endpoint for the plugin."""
    # In a real plugin, you might use self.api here if you had access to it from the router
    # or if the router was created within the plugin instance method that has `self`.
    # This example keeps the router definition self-contained for clarity.
    return {"status": "success", "received_data": data, "plugin_response": "Data processed by My Web API Plugin."}

@plugin_web_router.get(
    "/ui",
    response_class=JSONResponse,
    name="My Plugin UI",
    tags=["plugin-ui-native"]  # <--- This tag enables the Native UI renderer
)
async def get_plugin_ui():
    """Serves a custom JSON UI page from the plugin."""
    return JSONResponse(content={
        "type": "Container",
        "children": [
            {
                "type": "Text",
                "props": {"content": "Hello from My Web Plugin's Custom JSON UI Page!", "variant": "h1"}
            }
        ]
    })

class MyWebAPIPlugin(PluginBase):
    version = "1.2.0" # Mandatory

    def on_load(self):
        self.logger.info(f"{self.name} v{self.version} loaded.")
        if not HAS_AUTH_DEP:
            self.logger.warning("Auth dependency 'get_current_active_user' not found. Plugin API endpoints might be unsecured.")

    def get_fastapi_routers(self):
        self.logger.info(f"Providing FastAPI router for '/my_web_plugin'.")
        return [plugin_web_router] # Return a list containing your router(s)
```

After enabling `my_web_api_plugin.py` and restarting the Bedrock Server Manager web server, you could access:

*   `GET /my_web_plugin/info` (API endpoint)
*   `POST /my_web_plugin/submit_data` (API endpoint, with a JSON body)
*   `GET /my_web_plugin/ui` (Native JSON UI Page - visible in the Web Sidebar under Plugins)

These endpoints will also be listed in the OpenAPI documentation (e.g., at `/api/openapi.json` or `/docs`).

#### 6.1.1. Native JSON UI

Bedrock Server Manager allows plugins to define native UI pages using a simple JSON schema. This eliminates the need for plugin developers to write frontend code (React, HTML, CSS) while still providing a rich, interactive user interface that matches the application's look and feel.

Instead of serving HTML or Jinja2 templates, your plugin defines a FastAPI route that returns a JSON response. This route is tagged with `plugin-ui-native`. The frontend detects this tag and renders the JSON using a dynamic component renderer.

For more information and available components, refer to the [Native JSON UI](./native_json_ui.md) documentation.

```{tip}
**Tips for Plugin Web Endpoints:**

*   **Unique Prefixes & Mount Names:** Essential for routers and static mounts to avoid conflicts.
*   **Authentication:** Apply as needed to your plugin's routers or individual routes.
*  **Native JSON UI:** Tag your JSON UI routers with `plugin-ui-native` to have it added to the Web UI.
```

## 7. Best Practices

```{tip}
*   **Always use `self.logger`:** Do not use `print()`. The provided logger is integrated with the application's logging system.
*   **Handle exceptions:** Wrap API calls in `try...except` blocks to handle potential failures gracefully.
*   **Check the `result` dictionary:** After an `after_*` event, inspect the `result['status']` to confirm the outcome.
*   **Avoid blocking operations:** Long-running tasks in your event handlers or FastAPI endpoints can freeze the application. Use the [Task Manager](./task_manager.md) to offload them to background threads.
*   **Use the API for operations:** Do not directly manipulate server files or directories. Use the provided `self.api` functions to ensure thread-safety and consistency.
```
