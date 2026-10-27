# Scheduler plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `scheduler.list_schedules`
```python
await self.api.scheduler.list_schedules(request: bedrock_server_manager.api.models.scheduler.ListSchedulesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read schedule configuration, availability and bounded last-run metadata.

- **Returns:** `ListSchedulesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListSchedulesRequest
payload = {}
request = ListSchedulesRequest(**payload)
result = await self.api.scheduler.list_schedules(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ListSchedulesRequest](models.md#listschedulesrequest)
- **Response schema:** [ListSchedulesResponse](models.md#listschedulesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.scheduler.ListSchedulesRequest` | `REQUIRED` |
