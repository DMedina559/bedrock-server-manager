# Properties plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `properties.get_properties`
```python
await self.api.properties.get_properties(request: bedrock_server_manager.api.models.properties.GetPropertiesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the current server properties for a given server.

- **Returns:** `GetPropertiesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetPropertiesRequest
payload = {'server_name': 'example'}
request = GetPropertiesRequest(**payload)
result = await self.api.properties.get_properties(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetPropertiesRequest](models.md#getpropertiesrequest)
- **Response schema:** [GetPropertiesResponse](models.md#getpropertiesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.properties.GetPropertiesRequest` | `REQUIRED` |

---


## `properties.get_raw_properties`
```python
await self.api.properties.get_raw_properties(request: bedrock_server_manager.api.models.properties.GetRawPropertiesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read the complete properties document without parsing its keys or comments.

- **Returns:** `GetRawPropertiesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetRawPropertiesRequest
payload = {'server_name': 'example'}
request = GetRawPropertiesRequest(**payload)
result = await self.api.properties.get_raw_properties(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [GetRawPropertiesRequest](models.md#getrawpropertiesrequest)
- **Response schema:** [GetRawPropertiesResponse](models.md#getrawpropertiesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.properties.GetRawPropertiesRequest` | `REQUIRED` |

---


## `properties.set_properties`
```python
await self.api.properties.set_properties(request: bedrock_server_manager.api.models.properties.SetPropertiesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Set one or multiple server properties for a given server.

- **Returns:** `SetPropertiesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetPropertiesRequest
payload = {...}  # Supply required request fields below.
request = SetPropertiesRequest(**payload)
result = await self.api.properties.set_properties(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [SetPropertiesRequest](models.md#setpropertiesrequest)
- **Response schema:** [SetPropertiesResponse](models.md#setpropertiesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.properties.SetPropertiesRequest` | `REQUIRED` |

---


## `properties.validate_property_value`
```python
self.api.properties.validate_property_value(request: bedrock_server_manager.api.models.properties.ValidatePropertyValueRequest)
```
- **Async (Requires await):** No

- **Description:** Validates a specific server property value before it gets applied.

- **Returns:** `ValidatePropertyValueResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ValidatePropertyValueRequest
payload = {...}  # Supply required request fields below.
request = ValidatePropertyValueRequest(**payload)
result = self.api.properties.validate_property_value(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ValidatePropertyValueRequest](models.md#validatepropertyvaluerequest)
- **Response schema:** [ValidatePropertyValueResponse](models.md#validatepropertyvalueresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.properties.ValidatePropertyValueRequest` | `REQUIRED` |
