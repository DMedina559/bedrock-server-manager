# Websocket plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `websocket.websocket_broadcast`
```python
await self.api.websocket.websocket_broadcast(request: bedrock_server_manager.api.models.websocket.BroadcastRequest)
```
- **Async (Requires await):** Yes

- **Description:** Broadcasts a JSON payload to all WebSocket clients subscribed to a given topic.

- **Returns:** `BroadcastResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import BroadcastRequest
payload = {...}  # Supply required request fields below.
request = BroadcastRequest(**payload)
result = await self.api.websocket.websocket_broadcast(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [BroadcastRequest](models.md#broadcastrequest)
- **Response schema:** [BroadcastResponse](models.md#broadcastresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.BroadcastRequest` | `REQUIRED` |

---


## `websocket.websocket_publish_ws_event`
```python
await self.api.websocket.websocket_publish_ws_event(request: bedrock_server_manager.api.models.websocket.PublishWsEventRequest)
```
- **Async (Requires await):** Yes

- **Description:** Publishes a custom WebSocket event to topic 'ws_event:{event_name}'.

- **Returns:** `PublishWsEventResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import PublishWsEventRequest
payload = {...}  # Supply required request fields below.
request = PublishWsEventRequest(**payload)
result = await self.api.websocket.websocket_publish_ws_event(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [PublishWsEventRequest](models.md#publishwseventrequest)
- **Response schema:** [PublishWsEventResponse](models.md#publishwseventresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.PublishWsEventRequest` | `REQUIRED` |

---


## `websocket.websocket_send_to_client`
```python
await self.api.websocket.websocket_send_to_client(request: bedrock_server_manager.api.models.websocket.SendToClientRequest)
```
- **Async (Requires await):** Yes

- **Description:** Sends a JSON payload directly to a specific connected WebSocket client ID.

- **Returns:** `SendToClientResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SendToClientRequest
payload = {...}  # Supply required request fields below.
request = SendToClientRequest(**payload)
result = await self.api.websocket.websocket_send_to_client(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [SendToClientRequest](models.md#sendtoclientrequest)
- **Response schema:** [SendToClientResponse](models.md#sendtoclientresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.SendToClientRequest` | `REQUIRED` |

---


## `websocket.websocket_send_to_user`
```python
await self.api.websocket.websocket_send_to_user(request: bedrock_server_manager.api.models.websocket.SendToUserRequest)
```
- **Async (Requires await):** Yes

- **Description:** Sends a JSON payload to all active WebSocket connections belonging to a user.

- **Returns:** `SendToUserResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SendToUserRequest
payload = {...}  # Supply required request fields below.
request = SendToUserRequest(**payload)
result = await self.api.websocket.websocket_send_to_user(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [SendToUserRequest](models.md#sendtouserrequest)
- **Response schema:** [SendToUserResponse](models.md#sendtouserresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.SendToUserRequest` | `REQUIRED` |

---


## `websocket.websocket_unregister_data_provider`
```python
await self.api.websocket.websocket_unregister_data_provider(request: bedrock_server_manager.api.models.websocket.UnregisterDataProviderRequest)
```
- **Async (Requires await):** Yes

- **Description:** Unregisters a data provider handler for a WebSocket topic.

- **Returns:** `UnregisterDataProviderResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import UnregisterDataProviderRequest
payload = {...}  # Supply required request fields below.
request = UnregisterDataProviderRequest(**payload)
result = await self.api.websocket.websocket_unregister_data_provider(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [UnregisterDataProviderRequest](models.md#unregisterdataproviderrequest)
- **Response schema:** [UnregisterDataProviderResponse](models.md#unregisterdataproviderresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.UnregisterDataProviderRequest` | `REQUIRED` |
