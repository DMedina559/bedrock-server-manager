# Settings plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `settings.get_all_global_settings`
```python
await self.api.settings.get_all_global_settings(request: bedrock_server_manager.models.settings.GetAllGlobalSettingsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads the entire global application settings configuration.

- **Required Permission:** `settings:read`

- **Returns:** `GetAllGlobalSettingsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetAllGlobalSettingsRequest
request = GetAllGlobalSettingsRequest()
result = await self.api.settings.get_all_global_settings(request)
```
- **Request schema:** [GetAllGlobalSettingsRequest](models.md#getallglobalsettingsrequest)
- **Response schema:** [GetAllGlobalSettingsResponse](models.md#getallglobalsettingsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.settings.GetAllGlobalSettingsRequest` | `REQUIRED` |

---


## `settings.get_global_setting`
```python
await self.api.settings.get_global_setting(request: bedrock_server_manager.models.settings.GetGlobalSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads a single value from the global application settings.

- **Permission (key=paths.servers):** `path:servers`

- **Permission (key=paths.backups):** `path:backups`

- **Permission (key=paths.content):** `path:content`

- **Permission (key=paths.downloads):** `path:downloads`

- **Permission (key=paths.themes):** `path:themes`

- **Permission (non-path setting):** `settings:read`

- **Returns:** `GetGlobalSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import GetGlobalSettingRequest
request = GetGlobalSettingRequest(key=...)
result = await self.api.settings.get_global_setting(request)
```
- **Request schema:** [GetGlobalSettingRequest](models.md#getglobalsettingrequest)
- **Response schema:** [GetGlobalSettingResponse](models.md#getglobalsettingresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.settings.GetGlobalSettingRequest` | `REQUIRED` |

---


## `settings.set_custom_global_setting`
```python
await self.api.settings.set_custom_global_setting(request: bedrock_server_manager.models.settings.SetCustomGlobalSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Writes a custom value to the global application settings.

- **Required Permission:** `settings:manage`

- **Returns:** `SetCustomGlobalSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import SetCustomGlobalSettingRequest
request = SetCustomGlobalSettingRequest(key=..., value=...)
result = await self.api.settings.set_custom_global_setting(request)
```
- **Request schema:** [SetCustomGlobalSettingRequest](models.md#setcustomglobalsettingrequest)
- **Response schema:** [SetCustomGlobalSettingResponse](models.md#setcustomglobalsettingresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.settings.SetCustomGlobalSettingRequest` | `REQUIRED` |
