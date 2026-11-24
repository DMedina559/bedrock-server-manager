# Custom FastAPI endpoints

Plugins can add routes declaratively by setting `self.router` or `self.routers`
(or declaring `router` / `routers` on the plugin class). Give routes unique paths
and `operation_id` values so clients can discover them through OpenAPI. Define
Pydantic input and output models for your own data.

Use the authentication dependencies exported by `bedrock_server_manager`:
`get_current_user` for authenticated users, `get_moderator_user` for moderators
and admins, `get_admin_user` for admins, and `require_permissions` for
permission-scoped routes. Import these directly; an import failure must not
silently remove authentication.

```python
from fastapi import APIRouter, Depends, Security
from pydantic import BaseModel, ConfigDict
from bedrock_server_manager import (
    PluginBase,
    app_event,
    get_admin_user,
    require_permissions,
)

class PluginInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plugin_name: str
    message: str

class MyWebPlugin(PluginBase):
    version = "4.0.0"
    http_permissions = [
        ("view", "View plugin status", ["user", "moderator", "admin"]),
    ]

    @app_event("on_load")
    async def on_load(self, **kwargs):
        self.router = APIRouter(
            prefix="/my_web_plugin",
            tags=["My Web Plugin"],
            dependencies=[Depends(get_admin_user)],
        )

        @self.router.get(
            "/info",
            operation_id="my_web_plugin_info",
            response_model=PluginInfo,
            dependencies=[
                Security(require_permissions, scopes=["plugin:my_web_plugin:view"])
            ],
        )
        async def info():
            return PluginInfo(plugin_name=self.name, message="API is active.")
```

Enable the plugin to register its routes in the running web server. The example
adds `GET /my_web_plugin/info`. It also appears in the application's OpenAPI
schema and API documentation.

Declare custom HTTP permissions with `http_permissions` on the plugin class or instance, using 2-, 3-, or 4-tuples `(permission, description[, default_roles[, server_scoped]])` or dictionaries `{"permission": ..., "description": ..., "default_roles": [...], "server_scoped": bool}`. Omitting the `plugin:` prefix automatically prefixes `plugin:<plugin_name>:`. Permission names must match `^plugin:[A-Za-z0-9_.-]+:[a-z][a-z0-9_-]*(?::[a-z][a-z0-9_-]*)*$`, `default_roles` may only include `"user"`, `"moderator"`, and `"admin"` (defaulting to `["admin"]`), and `server_scoped=True` marks the permission as eligible for per-server access grants.

## Static asset mounts (`static_mounts`)

Declare static asset directories with `static_mounts = [(mount_prefix, local_dir_path, route_name)]`. BSM validates each mount before exposing it over HTTP:

- **`mount_prefix`:** Must start with `/<plugin_name>` or `/api/plugins/<plugin_name>` and cannot contain `..` or `//`.
- **Allowed directory roots (`local_dir_path`):** Static mounts may **only** serve directories located inside one of these three roots:
  1. `<plugin_dir>/<plugin_name>/...` — requires your plugin to be structured as a **package directory** (`<data_dir>/plugins/<plugin_name>/__init__.py`) so `Path(__file__).parent / "static"` resolves inside `<plugin_dir>/<plugin_name>/static`. A single-file plugin (`<data_dir>/plugins/my_plugin.py`) cannot mount `Path(__file__).parent / "static"` because that points outside `<plugin_dir>/<plugin_name>/`.
  2. `<config_dir>/plugins/<plugin_name>/...` — your plugin's private data directory (resolved via `await self.api.runtime.get_plugin_data_path(..., scope="private")`).
  3. `<config_dir>/plugins/public/...` — the shared public plugin data directory (resolved via `await self.api.runtime.get_plugin_data_path(..., scope="public")`).
- **No symlinks:** Symbolic links anywhere in the mounted directory chain are rejected.

The legacy imperative methods `get_fastapi_routers()`, `get_static_mounts()`, and `self.api.runtime.register_http_permission()` remain supported for compatibility but log deprecation warnings.

Use `self.api` inside route closures for supported server operations. Do not
reach into application context or database sessions.

For a page rendered by the web UI, tag its route `plugin-json-ui` and return the
JSON component schema described in [Native JSON UI](native_json_ui.md). Apply
authentication to UI routes too.

## Router resources

Use an async router lifespan for resources that belong to your endpoints. BSM
enters the lifespan when the web application starts, or when the plugin is
loaded into a running application. Unloading or reloading the plugin closes its
router resources. If startup fails, already opened router resources are closed
and the plugin is not activated.

Keep resources on the plugin instance or in endpoint closures so they are
available after a live reload:

```python
from contextlib import asynccontextmanager
from fastapi import APIRouter
from bedrock_server_manager import PluginBase, app_event

class MyResourcePlugin(PluginBase):
    version = "4.0.0"

    @app_event("on_load")
    async def on_load(self, **kwargs):
        @asynccontextmanager
        async def lifespan(app):
            self.client = await open_client()
            try:
                yield
            finally:
                await self.client.close()

        self.router = APIRouter(lifespan=lifespan)
        # Define authenticated endpoints that use self.client here.
```

Replace `open_client()` with your resource's initialization function. Lifespan
startup and cleanup run in the same task on the web application's event loop,
so task groups and cancellation scopes can remain open across the lifespan.
Keep lifespan callbacks focused on resource setup and cleanup; recursively
loading, unloading, or reloading plugins from them raises an error.
