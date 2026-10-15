# Permissions plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `permissions.get_permissions`
```python
await self.api.permissions.get_permissions(request: bedrock_server_manager.api.models.permissions.GetPermissionsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the permissions configuration for a server, formatted with player names.

- **Returns:** `GetPermissionsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetPermissionsRequest
payload = {'server_name': 'example'}
request = GetPermissionsRequest(**payload)
result = await self.api.permissions.get_permissions(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetPermissionsRequest](models.md#getpermissionsrequest)
- **Response schema:** [GetPermissionsResponse](models.md#getpermissionsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.permissions.GetPermissionsRequest` | `REQUIRED` |

---


## `permissions.set_permissions`
```python
await self.api.permissions.set_permissions(request: bedrock_server_manager.api.models.permissions.SetPermissionsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Set a player's permission level for a given server.

- **Returns:** `SetPermissionsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetPermissionsRequest
payload = {...}  # Supply required request fields below.
request = SetPermissionsRequest(**payload)
result = await self.api.permissions.set_permissions(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [SetPermissionsRequest](models.md#setpermissionsrequest)
- **Response schema:** [SetPermissionsResponse](models.md#setpermissionsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.permissions.SetPermissionsRequest` | `REQUIRED` |
