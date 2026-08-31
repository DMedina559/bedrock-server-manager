# Custom FastAPI Endpoints

## Extending Web Functionality

Plugins can significantly extend Bedrock Server Manager by adding their own custom FastAPI web endpoints. This allows for deep integration and tailored functionality.

To enable this, your plugin class (derived from `PluginBase`) needs to override one or both of the following methods:

*   **`get_fastapi_routers(self) -> List[fastapi.APIRouter]`**:
    This method should return a list of FastAPI `APIRouter` instances that your plugin wants to add to the main web application.

The Plugin Manager will call these methods on your plugin instance after it's loaded. The collected commands and routers are then integrated into the main application.

### Adding Custom FastAPI Endpoints (Web APIs and Pages)

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

from bedrock_server_manager import app_event

class MyWebAPIPlugin(PluginBase):
    version = "1.2.0" # Mandatory

    @app_event("on_load")
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

#### Native JSON UI

Bedrock Server Manager allows plugins to define native UI pages using a simple JSON schema. This eliminates the need for plugin developers to write frontend code (React, HTML, CSS) while still providing a rich, interactive user interface that matches the application's look and feel.

Instead of serving HTML or Jinja2 templates, your plugin defines a FastAPI route that returns a JSON response. This route is tagged with `plugin-ui-native`. The frontend detects this tag and renders the JSON using a dynamic component renderer.

For more information and available components, refer to the [Native JSON UI](./native_json_ui.md) documentation.

```{tip}
**Tips for Plugin Web Endpoints:**

*   **Unique Prefixes & Mount Names:** Essential for routers and static mounts to avoid conflicts.
*   **Authentication:** Apply as needed to your plugin's routers or individual routes.
*  **Native JSON UI:** Tag your JSON UI routers with `plugin-ui-native` to have it added to the Web UI.
```
