# Custom FastAPI endpoints

Plugins can add routes by returning `APIRouter` instances from
`get_fastapi_routers()`. Give routes unique paths and `operation_id` values so
clients can discover them through OpenAPI. Define Pydantic input and output
models for your own data.

Use the authentication dependencies exported by `bedrock_server_manager.web`:
`get_current_user` for authenticated users, `get_moderator_user` for moderators
and admins, and `get_admin_user` for admins. Import these directly; an import
failure must not silently remove authentication.

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from bedrock_server_manager import PluginBase
from bedrock_server_manager.web import get_admin_user

class PluginInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plugin_name: str
    message: str

class MyWebPlugin(PluginBase):
    version = "4.0.0"

    def get_fastapi_routers(self):
        router = APIRouter(
            prefix="/my_web_plugin", tags=["My Web Plugin"],
            dependencies=[Depends(get_admin_user)],
        )

        @router.get("/info", operation_id="my_web_plugin_info",
                    response_model=PluginInfo)
        async def info():
            return PluginInfo(plugin_name=self.name, message="API is active.")

        return [router]
```

Enable the plugin and restart the web server to register its routes. The example
adds `GET /my_web_plugin/info`. It also appears in the application's OpenAPI
schema and API documentation.

Use `self.api` inside route closures for supported server operations. Do not
reach into application context or database sessions.

For a page rendered by the web UI, tag its route `plugin-json-ui` and return the
JSON component schema described in [Native JSON UI](native_json_ui.md). Apply
authentication to UI routes too.
