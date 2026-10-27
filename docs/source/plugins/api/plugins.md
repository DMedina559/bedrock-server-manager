# Plugins plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `plugins.get_plugin_setting`
```python
await self.api.plugins.get_plugin_setting(request: bedrock_server_manager.api.models.plugins.GetPluginSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read settings scoped to the bridge-injected plugin identity.

- **Returns:** `GetPluginSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetPluginSettingRequest
payload = {}
request = GetPluginSettingRequest(**payload)
result = await self.api.plugins.get_plugin_setting(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetPluginSettingRequest](models.md#getpluginsettingrequest)
- **Response schema:** [GetPluginSettingResponse](models.md#getpluginsettingresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.plugins.GetPluginSettingRequest` | `REQUIRED` |

---


## `plugins.get_plugin_statuses`
```python
await self.api.plugins.get_plugin_statuses(request: bedrock_server_manager.api.models.plugins.GetPluginStatusesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the statuses and metadata of all discovered plugins.

- **Returns:** `GetPluginStatusesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetPluginStatusesRequest
payload = {}
request = GetPluginStatusesRequest(**payload)
result = await self.api.plugins.get_plugin_statuses(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetPluginStatusesRequest](models.md#getpluginstatusesrequest)
- **Response schema:** [GetPluginStatusesResponse](models.md#getpluginstatusesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.plugins.GetPluginStatusesRequest` | `REQUIRED` |

---


## `plugins.set_plugin_setting`
```python
await self.api.plugins.set_plugin_setting(request: bedrock_server_manager.api.models.plugins.SetPluginSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Persist settings scoped to the bridge-injected plugin identity.

- **Returns:** `SetPluginSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetPluginSettingRequest
payload = {...}  # Supply required request fields below.
request = SetPluginSettingRequest(**payload)
result = await self.api.plugins.set_plugin_setting(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [SetPluginSettingRequest](models.md#setpluginsettingrequest)
- **Response schema:** [SetPluginSettingResponse](models.md#setpluginsettingresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.plugins.SetPluginSettingRequest` | `REQUIRED` |
