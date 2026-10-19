# Server plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `server.get_all_settings`
```python
await self.api.server.get_all_settings(request: bedrock_server_manager.api.models.server.GetAllServerSettingsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads the entire persisted configurationuration for a specific server from its

- **Returns:** `GetAllServerSettingsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllServerSettingsRequest
payload = {'server_name': 'example'}
request = GetAllServerSettingsRequest(**payload)
result = await self.api.server.get_all_settings(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetAllServerSettingsRequest](models.md#getallserversettingsrequest)
- **Response schema:** [GetAllServerSettingsResponse](models.md#getallserversettingsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.GetAllServerSettingsRequest` | `REQUIRED` |

---


## `server.get_setting`
```python
await self.api.server.get_setting(request: bedrock_server_manager.api.models.server.GetServerSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads any value from a server's specific persisted configuration

- **Returns:** `GetServerSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetServerSettingRequest
payload = {...}  # Supply required request fields below.
request = GetServerSettingRequest(**payload)
result = await self.api.server.get_setting(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetServerSettingRequest](models.md#getserversettingrequest)
- **Response schema:** [GetServerSettingResponse](models.md#getserversettingresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.GetServerSettingRequest` | `REQUIRED` |

---


## `server.get_summary`
```python
await self.api.server.get_summary(request: bedrock_server_manager.api.models.server.GetServerSummaryRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the summary information for a specific server.

- **Returns:** `GetServerSummaryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetServerSummaryRequest
payload = {'server_name': 'example'}
request = GetServerSummaryRequest(**payload)
result = await self.api.server.get_summary(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetServerSummaryRequest](models.md#getserversummaryrequest)
- **Response schema:** [GetServerSummaryResponse](models.md#getserversummaryresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.GetServerSummaryRequest` | `REQUIRED` |

---


## `server.get_valid_names`
```python
await self.api.server.get_valid_names(request: bedrock_server_manager.api.models.server.GetValidServerNamesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return current registered server names without sampling processes.

- **Returns:** `GetValidServerNamesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetValidServerNamesRequest
payload = {}
request = GetValidServerNamesRequest(**payload)
result = await self.api.server.get_valid_names(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetValidServerNamesRequest](models.md#getvalidservernamesrequest)
- **Response schema:** [GetValidServerNamesResponse](models.md#getvalidservernamesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.GetValidServerNamesRequest` | `REQUIRED` |

---


## `server.restart`
```python
await self.api.server.restart(request: bedrock_server_manager.api.models.server.RestartServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Orchestrate stop/start; abort on cancellation or either phase failing.

- **Returns:** `RestartServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestartServerRequest
payload = {'server_name': 'example'}
request = RestartServerRequest(**payload)
result = await self.api.server.restart(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [RestartServerRequest](models.md#restartserverrequest)
- **Response schema:** [RestartServerResponse](models.md#restartserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.RestartServerRequest` | `REQUIRED` |

---


## `server.send_command`
```python
await self.api.server.send_command(request: bedrock_server_manager.api.models.server.SendCommandRequest)
```
- **Async (Requires await):** Yes

- **Description:** Sends a command to a running Bedrock server.

- **Returns:** `SendCommandResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SendCommandRequest
payload = {...}  # Supply required request fields below.
request = SendCommandRequest(**payload)
result = await self.api.server.send_command(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [SendCommandRequest](models.md#sendcommandrequest)
- **Response schema:** [SendCommandResponse](models.md#sendcommandresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.SendCommandRequest` | `REQUIRED` |

---


## `server.set_custom_value`
```python
await self.api.server.set_custom_value(request: bedrock_server_manager.api.models.server.SetServerCustomValueRequest)
```
- **Async (Requires await):** Yes

- **Description:** Writes a key-value pair to the 'custom' section of a server's specific

- **Returns:** `SetServerCustomValueResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetServerCustomValueRequest
payload = {...}  # Supply required request fields below.
request = SetServerCustomValueRequest(**payload)
result = await self.api.server.set_custom_value(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [SetServerCustomValueRequest](models.md#setservercustomvaluerequest)
- **Response schema:** [SetServerCustomValueResponse](models.md#setservercustomvalueresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.SetServerCustomValueRequest` | `REQUIRED` |

---


## `server.start`
```python
await self.api.server.start(request: bedrock_server_manager.api.models.server.StartServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Start an offline server under its lock, dispatching hooks only when needed.

- **Returns:** `StartServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import StartServerRequest
payload = {'server_name': 'example'}
request = StartServerRequest(**payload)
result = await self.api.server.start(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [StartServerRequest](models.md#startserverrequest)
- **Response schema:** [StartServerResponse](models.md#startserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.StartServerRequest` | `REQUIRED` |

---


## `server.stop`
```python
await self.api.server.stop(request: bedrock_server_manager.api.models.server.StopServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Stop a server, or report that it is already stopped; failures raise.

- **Returns:** `StopServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import StopServerRequest
payload = {'server_name': 'example'}
request = StopServerRequest(**payload)
result = await self.api.server.stop(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [StopServerRequest](models.md#stopserverrequest)
- **Response schema:** [StopServerResponse](models.md#stopserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.StopServerRequest` | `REQUIRED` |
