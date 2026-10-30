# System plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `system.get_application_health`
```python
await self.api.system.get_application_health(request: bedrock_server_manager.api.models.system.GetApplicationHealthRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read-only readiness checks; dependency errors never expose credentials.

- **Returns:** `GetApplicationHealthResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetApplicationHealthRequest
payload = {}
request = GetApplicationHealthRequest(**payload)
result = await self.api.system.get_application_health(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetApplicationHealthRequest](models.md#getapplicationhealthrequest)
- **Response schema:** [GetApplicationHealthResponse](models.md#getapplicationhealthresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.system.GetApplicationHealthRequest` | `REQUIRED` |

---


## `system.get_application_metrics`
```python
await self.api.system.get_application_metrics(request: bedrock_server_manager.api.models.system.GetApplicationMetricsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return shared, bounded performance history without sampling per request.

- **Returns:** `GetApplicationMetricsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetApplicationMetricsRequest
payload = {}
request = GetApplicationMetricsRequest(**payload)
result = await self.api.system.get_application_metrics(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetApplicationMetricsRequest](models.md#getapplicationmetricsrequest)
- **Response schema:** [GetApplicationMetricsResponse](models.md#getapplicationmetricsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.system.GetApplicationMetricsRequest` | `REQUIRED` |

---


## `system.get_bedrock_process_info`
```python
await self.api.system.get_bedrock_process_info(request: bedrock_server_manager.api.models.system.GetBedrockProcessInfoRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return resource usage for a running Bedrock server process.

- **Returns:** `GetBedrockProcessInfoResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetBedrockProcessInfoRequest
payload = {'server_name': 'example'}
request = GetBedrockProcessInfoRequest(**payload)
result = await self.api.system.get_bedrock_process_info(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetBedrockProcessInfoRequest](models.md#getbedrockprocessinforequest)
- **Response schema:** [GetBedrockProcessInfoResponse](models.md#getbedrockprocessinforesponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.system.GetBedrockProcessInfoRequest` | `REQUIRED` |

---


## `system.get_server_running_status`
```python
await self.api.system.get_server_running_status(request: bedrock_server_manager.api.models.system.GetServerRunningStatusRequest)
```
- **Async (Requires await):** Yes

- **Description:** Check if the server process is currently running.

- **Returns:** `GetServerRunningStatusResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetServerRunningStatusRequest
payload = {'server_name': 'example'}
request = GetServerRunningStatusRequest(**payload)
result = await self.api.system.get_server_running_status(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetServerRunningStatusRequest](models.md#getserverrunningstatusrequest)
- **Response schema:** [GetServerRunningStatusResponse](models.md#getserverrunningstatusresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.system.GetServerRunningStatusRequest` | `REQUIRED` |
