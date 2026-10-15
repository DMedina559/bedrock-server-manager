# World plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `world.export_world`
```python
await self.api.world.export_world(request: bedrock_server_manager.api.models.world.ExportWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Export the server's currently active world to a .mcworld archive.

- **Returns:** `ExportWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ExportWorldRequest
payload = {'server_name': 'example'}
request = ExportWorldRequest(**payload)
result = await self.api.world.export_world(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ExportWorldRequest](models.md#exportworldrequest)
- **Response schema:** [ExportWorldResponse](models.md#exportworldresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.world.ExportWorldRequest` | `REQUIRED` |

---


## `world.get_world_name`
```python
await self.api.world.get_world_name(request: bedrock_server_manager.api.models.world.GetWorldNameRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the configured world name (``level-name``) for a server.

- **Returns:** `GetWorldNameResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetWorldNameRequest
payload = {'server_name': 'example'}
request = GetWorldNameRequest(**payload)
result = await self.api.world.get_world_name(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetWorldNameRequest](models.md#getworldnamerequest)
- **Response schema:** [GetWorldNameResponse](models.md#getworldnameresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.world.GetWorldNameRequest` | `REQUIRED` |

---


## `world.import_world`
```python
await self.api.world.import_world(request: bedrock_server_manager.api.models.world.ImportWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Import a world from a .mcworld file, replacing the active world.

- **Returns:** `ImportWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ImportWorldRequest
payload = {...}  # Supply required request fields below.
request = ImportWorldRequest(**payload)
result = await self.api.world.import_world(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ImportWorldRequest](models.md#importworldrequest)
- **Response schema:** [ImportWorldResponse](models.md#importworldresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.world.ImportWorldRequest` | `REQUIRED` |
