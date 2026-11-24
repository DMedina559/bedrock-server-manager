# Ban plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `ban.add_server_ban`
```python
await self.api.ban.add_server_ban(request: bedrock_server_manager.models.ban.AddServerBanRequest)
```
- **Async (Requires await):** Yes

- **Description:** Adds a player to the server ban list.

- **Required Permission:** `bans:manage`

- **Returns:** `AddServerBanResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import AddServerBanRequest
request = AddServerBanRequest(player_name=..., xuid=..., server_name='example')
result = await self.api.ban.add_server_ban(request)
```
- **Request schema:** [AddServerBanRequest](models.md#addserverbanrequest)
- **Response schema:** [AddServerBanResponse](models.md#addserverbanresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.ban.AddServerBanRequest` | `REQUIRED` |

---


## `ban.get_server_bans`
```python
await self.api.ban.get_server_bans(request: bedrock_server_manager.models.ban.GetServerBansRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return all bans for a specific server.

- **Required Permission:** `bans:read`

- **Returns:** `GetServerBansResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetServerBansRequest
request = GetServerBansRequest(server_name='example')
result = await self.api.ban.get_server_bans(request)
```
- **Request schema:** [GetServerBansRequest](models.md#getserverbansrequest)
- **Response schema:** [GetServerBansResponse](models.md#getserverbansresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.ban.GetServerBansRequest` | `REQUIRED` |

---


## `ban.remove_server_ban`
```python
await self.api.ban.remove_server_ban(request: bedrock_server_manager.models.ban.RemoveServerBanRequest)
```
- **Async (Requires await):** Yes

- **Description:** Remove a player from the server ban list.

- **Required Permission:** `bans:manage`

- **Returns:** `RemoveServerBanResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import RemoveServerBanRequest
request = RemoveServerBanRequest(xuid=..., server_name='example')
result = await self.api.ban.remove_server_ban(request)
```
- **Request schema:** [RemoveServerBanRequest](models.md#removeserverbanrequest)
- **Response schema:** [RemoveServerBanResponse](models.md#removeserverbanresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.ban.RemoveServerBanRequest` | `REQUIRED` |
