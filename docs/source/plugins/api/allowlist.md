# Allowlist plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `allowlist.add_to_allowlist`
```python
await self.api.allowlist.add_to_allowlist(request: bedrock_server_manager.api.models.allowlist.AddToAllowlistRequest)
```
- **Async (Requires await):** Yes

- **Description:** Adds a list of players to the server's allowlist.

- **Returns:** `AddToAllowlistResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import AddToAllowlistRequest
payload = {...}  # Supply required request fields below.
request = AddToAllowlistRequest(**payload)
result = await self.api.allowlist.add_to_allowlist(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [AddToAllowlistRequest](models.md#addtoallowlistrequest)
- **Response schema:** [AddToAllowlistResponse](models.md#addtoallowlistresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.allowlist.AddToAllowlistRequest` | `REQUIRED` |

---


## `allowlist.get_allowlist`
```python
await self.api.allowlist.get_allowlist(request: bedrock_server_manager.api.models.allowlist.GetAllowlistRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the current allowlist for a given server.

- **Returns:** `GetAllowlistResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllowlistRequest
payload = {'server_name': 'example'}
request = GetAllowlistRequest(**payload)
result = await self.api.allowlist.get_allowlist(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetAllowlistRequest](models.md#getallowlistrequest)
- **Response schema:** [GetAllowlistResponse](models.md#getallowlistresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.allowlist.GetAllowlistRequest` | `REQUIRED` |

---


## `allowlist.remove_from_allowlist`
```python
await self.api.allowlist.remove_from_allowlist(request: bedrock_server_manager.api.models.allowlist.RemoveFromAllowlistRequest)
```
- **Async (Requires await):** Yes

- **Description:** Remove a list of players from the server's allowlist.

- **Returns:** `RemoveFromAllowlistResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RemoveFromAllowlistRequest
payload = {...}  # Supply required request fields below.
request = RemoveFromAllowlistRequest(**payload)
result = await self.api.allowlist.remove_from_allowlist(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [RemoveFromAllowlistRequest](models.md#removefromallowlistrequest)
- **Response schema:** [RemoveFromAllowlistResponse](models.md#removefromallowlistresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.allowlist.RemoveFromAllowlistRequest` | `REQUIRED` |
