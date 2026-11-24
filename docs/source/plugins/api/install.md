# Install plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `install.install_new_server`
```python
await self.api.install.install_new_server(request: bedrock_server_manager.models.install.InstallNewServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Installs a new server instance.

- **Required Permission:** `servers:install`

- **Returns:** `InstallNewServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import InstallNewServerRequest
request = InstallNewServerRequest(server_name='example')
result = await self.api.install.install_new_server(request)
```
- **Request schema:** [InstallNewServerRequest](models.md#installnewserverrequest)
- **Response schema:** [InstallNewServerResponse](models.md#installnewserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.install.InstallNewServerRequest` | `REQUIRED` |

---


## `install.update_server`
```python
await self.api.install.update_server(request: bedrock_server_manager.models.install.UpdateServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Updates an existing server instance.

- **Required Permission:** `servers:install`

- **Returns:** `UpdateServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import UpdateServerRequest
request = UpdateServerRequest(server_name='example')
result = await self.api.install.update_server(request)
```
- **Request schema:** [UpdateServerRequest](models.md#updateserverrequest)
- **Response schema:** [UpdateServerResponse](models.md#updateserverresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.install.UpdateServerRequest` | `REQUIRED` |
