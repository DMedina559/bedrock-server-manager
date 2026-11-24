# World plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `world.export_world`
```python
await self.api.world.export_world(request: bedrock_server_manager.models.world.ExportWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Export the server's currently active world to a .mcworld archive.

- **Required Permission:** `worlds:manage`

- **Returns:** `ExportWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ExportWorldRequest
request = ExportWorldRequest(server_name='example')
result = await self.api.world.export_world(request)
```
- **Request schema:** [ExportWorldRequest](models.md#exportworldrequest)
- **Response schema:** [ExportWorldResponse](models.md#exportworldresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.world.ExportWorldRequest` | `REQUIRED` |

---


## `world.get_world_name`
```python
await self.api.world.get_world_name(request: bedrock_server_manager.models.world.GetWorldNameRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the configured world name (``level-name``) for a server.

- **Required Permission:** `worlds:read`

- **Returns:** `GetWorldNameResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetWorldNameRequest
request = GetWorldNameRequest(server_name='example')
result = await self.api.world.get_world_name(request)
```
- **Request schema:** [GetWorldNameRequest](models.md#getworldnamerequest)
- **Response schema:** [GetWorldNameResponse](models.md#getworldnameresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.world.GetWorldNameRequest` | `REQUIRED` |

---


## `world.import_world`
```python
await self.api.world.import_world(request: bedrock_server_manager.models.world.ImportWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Import a world from a .mcworld file, replacing the active world.

- **Required Permission:** `worlds:manage`

- **Returns:** `ImportWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ImportWorldRequest
request = ImportWorldRequest(server_name='example', selected_file_path=...)
result = await self.api.world.import_world(request)
```
- **Request schema:** [ImportWorldRequest](models.md#importworldrequest)
- **Response schema:** [ImportWorldResponse](models.md#importworldresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.world.ImportWorldRequest` | `REQUIRED` |

---


## `world.reset_world`
```python
await self.api.world.reset_world(request: bedrock_server_manager.models.world.ResetWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Resets the server's world by deleting the active world directory.

- **Required Permission:** `worlds:reset`

- **Returns:** `ResetWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ResetWorldRequest
request = ResetWorldRequest(server_name='example')
result = await self.api.world.reset_world(request)
```
- **Request schema:** [ResetWorldRequest](models.md#resetworldrequest)
- **Response schema:** [ResetWorldResponse](models.md#resetworldresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.world.ResetWorldRequest` | `REQUIRED` |
