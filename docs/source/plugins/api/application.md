# Application plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `application.get_all_servers_data`
```python
await self.api.application.get_all_servers_data(request: bedrock_server_manager.models.application.GetAllServersDataRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return status and version for all detected servers.

- **Required Permission:** `servers:read`

- **Returns:** `GetAllServersDataResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetAllServersDataRequest
request = GetAllServersDataRequest()
result = await self.api.application.get_all_servers_data(request)
```
- **Request schema:** [GetAllServersDataRequest](models.md#getallserversdatarequest)
- **Response schema:** [GetAllServersDataResponse](models.md#getallserversdataresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.application.GetAllServersDataRequest` | `REQUIRED` |

---


## `application.get_system_and_app_info`
```python
self.api.application.get_system_and_app_info(request: bedrock_server_manager.models.application.GetSystemAndAppInfoRequest)
```
- **Async (Requires await):** No

- **Description:** Return basic system and application information.

- **Returns:** `GetSystemAndAppInfoResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetSystemAndAppInfoRequest
request = GetSystemAndAppInfoRequest()
result = self.api.application.get_system_and_app_info(request)
```
- **Request schema:** [GetSystemAndAppInfoRequest](models.md#getsystemandappinforequest)
- **Response schema:** [GetSystemAndAppInfoResponse](models.md#getsystemandappinforesponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.application.GetSystemAndAppInfoRequest` | `REQUIRED` |

---


## `application.list_available_worlds`
```python
await self.api.application.list_available_worlds(request: bedrock_server_manager.models.application.ListAvailableWorldsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists available .mcworld files from the content directory.

- **Required Permission:** `content:read`

- **Returns:** `ListAvailableWorldsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListAvailableWorldsRequest
request = ListAvailableWorldsRequest()
result = await self.api.application.list_available_worlds(request)
```
- **Request schema:** [ListAvailableWorldsRequest](models.md#listavailableworldsrequest)
- **Response schema:** [ListAvailableWorldsResponse](models.md#listavailableworldsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.application.ListAvailableWorldsRequest` | `REQUIRED` |
