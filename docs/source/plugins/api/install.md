# Install plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `install.install_new_server`
```python
await self.api.install.install_new_server(request: bedrock_server_manager.api.models.install.InstallNewServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Installs a new server instance.

- **Returns:** `InstallNewServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import InstallNewServerRequest
payload = {'server_name': 'example'}
request = InstallNewServerRequest(**payload)
result = await self.api.install.install_new_server(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [InstallNewServerRequest](models.md#installnewserverrequest)
- **Response schema:** [InstallNewServerResponse](models.md#installnewserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.install.InstallNewServerRequest` | `REQUIRED` |

---


## `install.update_server`
```python
await self.api.install.update_server(request: bedrock_server_manager.api.models.install.UpdateServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Updates an existing server instance.

- **Returns:** `UpdateServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import UpdateServerRequest
payload = {'server_name': 'example'}
request = UpdateServerRequest(**payload)
result = await self.api.install.update_server(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [UpdateServerRequest](models.md#updateserverrequest)
- **Response schema:** [UpdateServerResponse](models.md#updateserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.install.UpdateServerRequest` | `REQUIRED` |
