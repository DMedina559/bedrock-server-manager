# Server plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `server.get_all_settings`
```python
await self.api.server.get_all_settings(request: bedrock_server_manager.models.server.GetAllServerSettingsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads the entire persisted configurationuration for a specific server from its

- **Required Permission:** `servers:read`

- **Returns:** `GetAllServerSettingsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetAllServerSettingsRequest
request = GetAllServerSettingsRequest(server_name='example')
result = await self.api.server.get_all_settings(request)
```
- **Request schema:** [GetAllServerSettingsRequest](models.md#getallserversettingsrequest)
- **Response schema:** [GetAllServerSettingsResponse](models.md#getallserversettingsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.GetAllServerSettingsRequest` | `REQUIRED` |

---


## `server.get_process`
```python
await self.api.server.get_process(request: bedrock_server_manager.models.process.GetServerProcessRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return observed process capabilities independently of the server summary.

- **Required Permission:** `servers:inspect`

- **Returns:** `GetServerProcessResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetServerProcessRequest
request = GetServerProcessRequest(server_name='example')
result = await self.api.server.get_process(request)
```
- **Request schema:** [GetServerProcessRequest](models.md#getserverprocessrequest)
- **Response schema:** [GetServerProcessResponse](models.md#getserverprocessresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.process.GetServerProcessRequest` | `REQUIRED` |

---


## `server.get_setting`
```python
await self.api.server.get_setting(request: bedrock_server_manager.models.server.GetServerSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads any value from a server's specific persisted configuration

- **Required Permission:** `servers:read`

- **Returns:** `GetServerSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetServerSettingRequest
request = GetServerSettingRequest(server_name='example', key=...)
result = await self.api.server.get_setting(request)
```
- **Request schema:** [GetServerSettingRequest](models.md#getserversettingrequest)
- **Response schema:** [GetServerSettingResponse](models.md#getserversettingresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.GetServerSettingRequest` | `REQUIRED` |

---


## `server.get_summary`
```python
await self.api.server.get_summary(request: bedrock_server_manager.models.server.GetServerSummaryRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the summary information for a specific server.

- **Required Permission:** `servers:read`

- **Returns:** `GetServerSummaryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetServerSummaryRequest
request = GetServerSummaryRequest(server_name='example')
result = await self.api.server.get_summary(request)
```
- **Request schema:** [GetServerSummaryRequest](models.md#getserversummaryrequest)
- **Response schema:** [GetServerSummaryResponse](models.md#getserversummaryresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.GetServerSummaryRequest` | `REQUIRED` |

---


## `server.get_valid_names`
```python
await self.api.server.get_valid_names(request: bedrock_server_manager.models.server.GetValidServerNamesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return current registered server names without sampling processes.

- **Required Permission:** `servers:read`

- **Returns:** `GetValidServerNamesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetValidServerNamesRequest
request = GetValidServerNamesRequest()
result = await self.api.server.get_valid_names(request)
```
- **Request schema:** [GetValidServerNamesRequest](models.md#getvalidservernamesrequest)
- **Response schema:** [GetValidServerNamesResponse](models.md#getvalidservernamesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.GetValidServerNamesRequest` | `REQUIRED` |

---


## `server.restart`
```python
await self.api.server.restart(request: bedrock_server_manager.models.server.RestartServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Orchestrate stop/start; abort on cancellation or either phase failing.

- **Required Permission:** `servers:lifecycle`

- **Returns:** `RestartServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import RestartServerRequest
request = RestartServerRequest(server_name='example')
result = await self.api.server.restart(request)
```
- **Request schema:** [RestartServerRequest](models.md#restartserverrequest)
- **Response schema:** [RestartServerResponse](models.md#restartserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.RestartServerRequest` | `REQUIRED` |

---


## `server.send_command`
```python
await self.api.server.send_command(request: bedrock_server_manager.models.server.SendCommandRequest)
```
- **Async (Requires await):** Yes

- **Description:** Sends a command to a running Bedrock server.

- **Required Permission:** `servers:command`

- **Returns:** `SendCommandResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import SendCommandRequest
request = SendCommandRequest(command=..., server_name='example')
result = await self.api.server.send_command(request)
```
- **Request schema:** [SendCommandRequest](models.md#sendcommandrequest)
- **Response schema:** [SendCommandResponse](models.md#sendcommandresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.SendCommandRequest` | `REQUIRED` |

---


## `server.set_custom_value`
```python
await self.api.server.set_custom_value(request: bedrock_server_manager.models.server.SetServerCustomValueRequest)
```
- **Async (Requires await):** Yes

- **Description:** Writes a key-value pair to the 'custom' section of a server's specific

- **Returns:** `SetServerCustomValueResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import SetServerCustomValueRequest
request = SetServerCustomValueRequest(key=..., value=..., server_name='example')
result = await self.api.server.set_custom_value(request)
```
- **Request schema:** [SetServerCustomValueRequest](models.md#setservercustomvaluerequest)
- **Response schema:** [SetServerCustomValueResponse](models.md#setservercustomvalueresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.SetServerCustomValueRequest` | `REQUIRED` |

---


## `server.start`
```python
await self.api.server.start(request: bedrock_server_manager.models.server.StartServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Start an offline server under its lock, dispatching hooks only when needed.

- **Required Permission:** `servers:lifecycle`

- **Returns:** `StartServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import StartServerRequest
request = StartServerRequest(server_name='example')
result = await self.api.server.start(request)
```
- **Request schema:** [StartServerRequest](models.md#startserverrequest)
- **Response schema:** [StartServerResponse](models.md#startserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.StartServerRequest` | `REQUIRED` |

---


## `server.stop`
```python
await self.api.server.stop(request: bedrock_server_manager.models.server.StopServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Stop a server, or report that it is already stopped; failures raise.

- **Required Permission:** `servers:lifecycle`

- **Returns:** `StopServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import StopServerRequest
request = StopServerRequest(server_name='example')
result = await self.api.server.stop(request)
```
- **Request schema:** [StopServerRequest](models.md#stopserverrequest)
- **Response schema:** [StopServerResponse](models.md#stopserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.server.StopServerRequest` | `REQUIRED` |

---


## `server.wait_for_log`
```python
await self.api.server.wait_for_log(request: bedrock_server_manager.models.logs.WaitForServerLogRequest)
```
- **Async (Requires await):** Yes

- **Description:** Wait for owned live output, bounded and cancelled with its plugin owner.

- **Required Permission:** `logs:read`

- **Returns:** `WaitForServerLogResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import WaitForServerLogRequest
request = WaitForServerLogRequest(server_name='example', text=...)
result = await self.api.server.wait_for_log(request)
```
- **Request schema:** [WaitForServerLogRequest](models.md#waitforserverlogrequest)
- **Response schema:** [WaitForServerLogResponse](models.md#waitforserverlogresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.logs.WaitForServerLogRequest` | `REQUIRED` |
