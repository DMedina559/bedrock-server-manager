# Player plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `player.add_players_manually`
```python
await self.api.player.add_players_manually(request: bedrock_server_manager.api.models.player.AddPlayersManuallyRequest)
```
- **Async (Requires await):** Yes

- **Description:** Adds or updates player data in the database.

- **Returns:** `AddPlayersManuallyResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import AddPlayersManuallyRequest
payload = {...}  # Supply required request fields below.
request = AddPlayersManuallyRequest(**payload)
result = await self.api.player.add_players_manually(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [AddPlayersManuallyRequest](models.md#addplayersmanuallyrequest)
- **Response schema:** [AddPlayersManuallyResponse](models.md#addplayersmanuallyresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.player.AddPlayersManuallyRequest` | `REQUIRED` |

---


## `player.get_all_known_players`
```python
await self.api.player.get_all_known_players(request: bedrock_server_manager.api.models.player.GetAllKnownPlayersRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return all player data from the database.

- **Returns:** `GetAllKnownPlayersResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllKnownPlayersRequest
payload = {}
request = GetAllKnownPlayersRequest(**payload)
result = await self.api.player.get_all_known_players(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetAllKnownPlayersRequest](models.md#getallknownplayersrequest)
- **Response schema:** [GetAllKnownPlayersResponse](models.md#getallknownplayersresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.player.GetAllKnownPlayersRequest` | `REQUIRED` |

---


## `player.scan_and_update_player_db`
```python
await self.api.player.scan_and_update_player_db(request: bedrock_server_manager.api.models.player.ScanAndUpdatePlayerDbRequest)
```
- **Async (Requires await):** Yes

- **Description:** Scans all server logs to discover and save player data.

- **Returns:** `ScanAndUpdatePlayerDbResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ScanAndUpdatePlayerDbRequest
payload = {}
request = ScanAndUpdatePlayerDbRequest(**payload)
result = await self.api.player.scan_and_update_player_db(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ScanAndUpdatePlayerDbRequest](models.md#scanandupdateplayerdbrequest)
- **Response schema:** [ScanAndUpdatePlayerDbResponse](models.md#scanandupdateplayerdbresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.player.ScanAndUpdatePlayerDbRequest` | `REQUIRED` |
