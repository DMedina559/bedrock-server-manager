# Settings plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `settings.get_all_global_settings`
```python
await self.api.settings.get_all_global_settings(request: bedrock_server_manager.api.models.settings.GetAllGlobalSettingsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads the entire global application settings configuration.

- **Returns:** `GetAllGlobalSettingsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllGlobalSettingsRequest
payload = {}
request = GetAllGlobalSettingsRequest(**payload)
result = await self.api.settings.get_all_global_settings(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetAllGlobalSettingsRequest](models.md#getallglobalsettingsrequest)
- **Response schema:** [GetAllGlobalSettingsResponse](models.md#getallglobalsettingsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.settings.GetAllGlobalSettingsRequest` | `REQUIRED` |

---


## `settings.get_global_setting`
```python
await self.api.settings.get_global_setting(request: bedrock_server_manager.api.models.settings.GetGlobalSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads a single value from the global application settings.

- **Returns:** `GetGlobalSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetGlobalSettingRequest
payload = {...}  # Supply required request fields below.
request = GetGlobalSettingRequest(**payload)
result = await self.api.settings.get_global_setting(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetGlobalSettingRequest](models.md#getglobalsettingrequest)
- **Response schema:** [GetGlobalSettingResponse](models.md#getglobalsettingresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.settings.GetGlobalSettingRequest` | `REQUIRED` |

---


## `settings.set_custom_global_setting`
```python
await self.api.settings.set_custom_global_setting(request: bedrock_server_manager.api.models.settings.SetCustomGlobalSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Writes a custom value to the global application settings.

- **Returns:** `SetCustomGlobalSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetCustomGlobalSettingRequest
payload = {...}  # Supply required request fields below.
request = SetCustomGlobalSettingRequest(**payload)
result = await self.api.settings.set_custom_global_setting(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [SetCustomGlobalSettingRequest](models.md#setcustomglobalsettingrequest)
- **Response schema:** [SetCustomGlobalSettingResponse](models.md#setcustomglobalsettingresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.settings.SetCustomGlobalSettingRequest` | `REQUIRED` |
