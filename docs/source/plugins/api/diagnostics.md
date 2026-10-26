# Diagnostics plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `diagnostics.compare_diagnostic_snapshots`
```python
await self.api.diagnostics.compare_diagnostic_snapshots(request: bedrock_server_manager.api.models.diagnostics.CompareDiagnosticSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Compare metadata snapshots without treating restarted counters as activity.

- **Returns:** `CompareDiagnosticSnapshotsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import CompareDiagnosticSnapshotsRequest
payload = {...}  # Supply required request fields below.
request = CompareDiagnosticSnapshotsRequest(**payload)
result = await self.api.diagnostics.compare_diagnostic_snapshots(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [CompareDiagnosticSnapshotsRequest](models.md#comparediagnosticsnapshotsrequest)
- **Response schema:** [CompareDiagnosticSnapshotsResponse](models.md#comparediagnosticsnapshotsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.CompareDiagnosticSnapshotsRequest` | `REQUIRED` |

---


## `diagnostics.get_application_diagnostics`
```python
await self.api.diagnostics.get_application_diagnostics(request: bedrock_server_manager.api.models.diagnostics.GetApplicationDiagnosticsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read bounded subsystem metadata; unavailable providers remain isolated.

- **Returns:** `GetApplicationDiagnosticsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetApplicationDiagnosticsRequest
payload = {}
request = GetApplicationDiagnosticsRequest(**payload)
result = await self.api.diagnostics.get_application_diagnostics(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetApplicationDiagnosticsRequest](models.md#getapplicationdiagnosticsrequest)
- **Response schema:** [GetApplicationDiagnosticsResponse](models.md#getapplicationdiagnosticsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetApplicationDiagnosticsRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_activity`
```python
await self.api.diagnostics.get_diagnostic_activity(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticActivityRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read all-chain event, operation, and subscription metadata without payloads.

- **Returns:** `GetDiagnosticActivityResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticActivityRequest
payload = {}
request = GetDiagnosticActivityRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_activity(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetDiagnosticActivityRequest](models.md#getdiagnosticactivityrequest)
- **Response schema:** [GetDiagnosticActivityResponse](models.md#getdiagnosticactivityresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticActivityRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_history`
```python
await self.api.diagnostics.get_diagnostic_history(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticHistoryRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read sanitized retained records, optionally scoped to an application run.

- **Returns:** `GetDiagnosticHistoryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticHistoryRequest
payload = {}
request = GetDiagnosticHistoryRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_history(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetDiagnosticHistoryRequest](models.md#getdiagnostichistoryrequest)
- **Response schema:** [GetDiagnosticHistoryResponse](models.md#getdiagnostichistoryresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticHistoryRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_report`
```python
await self.api.diagnostics.get_diagnostic_report(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticReportRequest)
```
- **Async (Requires await):** Yes

- **Description:** Build a support report without secrets, task arguments, or event payloads.

- **Returns:** `GetDiagnosticReportResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticReportRequest
payload = {}
request = GetDiagnosticReportRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_report(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetDiagnosticReportRequest](models.md#getdiagnosticreportrequest)
- **Response schema:** [GetDiagnosticReportResponse](models.md#getdiagnosticreportresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticReportRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_runs`
```python
await self.api.diagnostics.get_diagnostic_runs(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticRunsRequest)
```
- **Async (Requires await):** Yes

- **Description:** List retained application instances without guessing whether older runs are alive.

- **Returns:** `GetDiagnosticRunsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticRunsRequest
payload = {}
request = GetDiagnosticRunsRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_runs(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetDiagnosticRunsRequest](models.md#getdiagnosticrunsrequest)
- **Response schema:** [GetDiagnosticRunsResponse](models.md#getdiagnosticrunsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticRunsRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_trace`
```python
await self.api.diagnostics.get_diagnostic_trace(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticTraceRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read events, tasks, and retained failures sharing one correlation identity.

- **Returns:** `GetDiagnosticTraceResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticTraceRequest
payload = {...}  # Supply required request fields below.
request = GetDiagnosticTraceRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_trace(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetDiagnosticTraceRequest](models.md#getdiagnostictracerequest)
- **Response schema:** [GetDiagnosticTraceResponse](models.md#getdiagnostictraceresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticTraceRequest` | `REQUIRED` |
