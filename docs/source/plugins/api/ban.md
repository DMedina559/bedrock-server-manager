# Ban plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `ban.add_server_ban`
```python
await self.api.ban.add_server_ban(request: bedrock_server_manager.api.models.ban.AddServerBanRequest)
```
- **Async (Requires await):** Yes

- **Description:** Adds a player to the server ban list.

- **Returns:** `AddServerBanResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import AddServerBanRequest
payload = {...}  # Supply required request fields below.
request = AddServerBanRequest(**payload)
result = await self.api.ban.add_server_ban(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [AddServerBanRequest](models.md#addserverbanrequest)
- **Response schema:** [AddServerBanResponse](models.md#addserverbanresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.ban.AddServerBanRequest` | `REQUIRED` |

---


## `ban.get_server_bans`
```python
await self.api.ban.get_server_bans(request: bedrock_server_manager.api.models.ban.GetServerBansRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return all bans for a specific server.

- **Returns:** `GetServerBansResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetServerBansRequest
payload = {'server_name': 'example'}
request = GetServerBansRequest(**payload)
result = await self.api.ban.get_server_bans(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetServerBansRequest](models.md#getserverbansrequest)
- **Response schema:** [GetServerBansResponse](models.md#getserverbansresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.ban.GetServerBansRequest` | `REQUIRED` |

---


## `ban.remove_server_ban`
```python
await self.api.ban.remove_server_ban(request: bedrock_server_manager.api.models.ban.RemoveServerBanRequest)
```
- **Async (Requires await):** Yes

- **Description:** Remove a player from the server ban list.

- **Returns:** `RemoveServerBanResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RemoveServerBanRequest
payload = {...}  # Supply required request fields below.
request = RemoveServerBanRequest(**payload)
result = await self.api.ban.remove_server_ban(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [RemoveServerBanRequest](models.md#removeserverbanrequest)
- **Response schema:** [RemoveServerBanResponse](models.md#removeserverbanresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.ban.RemoveServerBanRequest` | `REQUIRED` |
