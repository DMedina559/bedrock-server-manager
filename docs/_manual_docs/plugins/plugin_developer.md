# Developing Plugins

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

This guide will walk you through creating your own plugins to extend and customize the Bedrock Server Manager. The plugin system is designed to be simple yet powerful, allowing you to hook into various application events and use the core application's functions safely.

This guide assumes you have a basic understanding of Python programming. 

For a complete list of all available event hooks, see the [Plugin Base](../../plugin_internals.rst).
For a complete list of all available event hooks, see the [Available APIs](./plugin_apis.md).

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

## 5. Extending Functionality: Custom CLI Commands and FastAPI Endpoints

Plugins can significantly extend Bedrock Server Manager by adding their own custom CLI commands and FastAPI web endpoints. This allows for deep integration and tailored functionality.

To enable this, your plugin class (derived from `PluginBase`) needs to override one or both of the following methods:

*   **`get_cli_commands(self) -> List[click.Command | click.Group]`**:
    This method should return a list of Click command or group objects that your plugin wants to add to the main `bedrock-server-manager` CLI.
*   **`get_fastapi_routers(self) -> List[fastapi.APIRouter]`**:
    This method should return a list of FastAPI `APIRouter` instances that your plugin wants to add to the main web application.

The Plugin Manager will call these methods on your plugin instance after it's loaded. The collected commands and routers are then integrated into the main application.

### 5.1. Adding Custom CLI Commands

To add CLI commands, define your Click commands/groups as usual and then return them in a list from `get_cli_commands()`.

**Example:**

```python
# my_cli_plugin.py
from bedrock_server_manager.plugins.plugin_base import PluginBase
import click

# Define a Click command group
@click.group("myplug")
def my_plugin_cli_group():
    """A custom command group from My CLI Plugin."""
    pass # This docstring will appear in 'bsm myplug --help'

@my_plugin_cli_group.command("greet")
@click.option('--name', default='CLI User', help='The person to greet.')
def greet_command(name):
    """Greets a user from the plugin's CLI."""
    click.echo(f"Hello, {name}, from My CLI Plugin!")

@my_plugin_cli_group.command("status")
def status_command():
    """Shows a custom status from the plugin."""
    click.echo("My CLI Plugin status: All systems nominal.")

class MyCLIPlugin(PluginBase):
    version = "1.1.0"  # Mandatory

    def on_load(self):
        self.logger.info(f"{self.name} v{self.version} loaded.")

    def get_cli_commands(self):
        self.logger.info(f"Providing CLI command group 'myplug' with its subcommands.")
        # Return the top-level group; Click handles its subcommands.
        return [my_plugin_cli_group] 
```

After enabling `my_cli_plugin.py`, the following commands would become available:

*   `bedrock-server-manager myplug --help`
*   `bedrock-server-manager myplug greet --name "Awesome Dev"`
*   `bedrock-server-manager myplug status`

### 5.2. Adding Custom FastAPI Endpoints (Web APIs and Pages)

To add web endpoints, define your FastAPI `APIRouter` instances and return them in a list from `get_fastapi_routers()`. These routers will be included in the main FastAPI application.

**Example:**

```python
# my_web_api_plugin.py
from bedrock_server_manager import PluginBase
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

# Attempt to import authentication dependency; provide a fallback for isolated testing/robustness
try:
    from bedrock_server_manager.web.auth_utils import get_current_user
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

@plugin_web_router.get("/custom-html-page", response_class=HTMLResponse)
async def get_plugin_custom_html():
    """Serves a custom HTML page from the plugin."""
    html_content = """
    <html>
        <head><title>My Plugin Page</title></head>
        <body><h1>Hello from My Web Plugin's Custom HTML Page!</h1></body>
    </html>
    """
    return HTMLResponse(content=html_content)

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
*   `GET /my_web_plugin/custom-html-page` (HTML page)

These endpoints will also be listed in the OpenAPI documentation (e.g., at `/api/openapi.json` or `/docs`).

```{tip}
**Tips for Plugin Web Endpoints:**

*   **Unique Prefixes:** Always use a unique `prefix` for your `APIRouter` (e.g., `/my_plugin_name`) to avoid conflicts with core application routes or other plugins.
*   **OpenAPI Tags:** Use the `tags` parameter in your `APIRouter` to group your plugin's endpoints clearly in the OpenAPI documentation.
*   **Authentication & Authorization:** You can secure your plugin's endpoints by adding FastAPI dependencies (like authentication checks) to your `APIRouter` or individual routes. You can import and use dependencies from `bedrock_server_manager.web.dependencies` if they suit your needs (as shown with `get_current_active_user`).
*   **Serving HTML:** As shown, you can return `fastapi.responses.HTMLResponse` to serve custom web pages directly from your plugin. For more complex UIs, consider if client-side rendering calling your plugin's APIs is more appropriate.
*   **Accessing `self.api` or `self.logger` from Routers:** If your route handlers need access to the plugin instance's `self.api` or `self.logger`, you'll need to define the router and its routes in a way that they can capture `self` (e.g., by defining routes as methods of a class that gets instantiated with `self`, or by creating the router instance within a method of your plugin class). The examples above define routers at the module level for simplicity.
```

## 6. Best Practices

```{tip}
*   **Always use `self.logger`:** Do not use `print()`. The provided logger is integrated with the application's logging system.
*   **Handle exceptions:** Wrap API calls in `try...except` blocks to handle potential failures gracefully.
*   **Check the `result` dictionary:** After an `after_*` event, inspect the `result['status']` to confirm the outcome.
*   **Avoid blocking operations:** Long-running tasks in your event handlers can freeze the application. Offload them to separate threads if necessary.
*   **Use the API for operations:** Do not directly manipulate server files or directories. Use the provided `self.api` functions to ensure thread-safety and consistency.
```