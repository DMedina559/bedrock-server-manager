# Addon plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `addon.disable_addon`
```python
await self.api.addon.disable_addon(request: bedrock_server_manager.api.models.addon.DisableAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Disables an active addon for a server's active world, preserving files.

- **Returns:** `DisableAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import DisableAddonRequest
payload = {...}  # Supply required request fields below.
request = DisableAddonRequest(**payload)
result = await self.api.addon.disable_addon(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [DisableAddonRequest](models.md#disableaddonrequest)
- **Response schema:** [DisableAddonResponse](models.md#disableaddonresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.DisableAddonRequest` | `REQUIRED` |

---


## `addon.enable_addon`
```python
await self.api.addon.enable_addon(request: bedrock_server_manager.api.models.addon.EnableAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Enables a disabled addon for a server's active world.

- **Returns:** `EnableAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import EnableAddonRequest
payload = {...}  # Supply required request fields below.
request = EnableAddonRequest(**payload)
result = await self.api.addon.enable_addon(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [EnableAddonRequest](models.md#enableaddonrequest)
- **Response schema:** [EnableAddonResponse](models.md#enableaddonresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.EnableAddonRequest` | `REQUIRED` |

---


## `addon.import_addon`
```python
await self.api.addon.import_addon(request: bedrock_server_manager.api.models.addon.ImportAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Installs an addon to a specified Bedrock server.

- **Returns:** `ImportAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ImportAddonRequest
payload = {...}  # Supply required request fields below.
request = ImportAddonRequest(**payload)
result = await self.api.addon.import_addon(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ImportAddonRequest](models.md#importaddonrequest)
- **Response schema:** [ImportAddonResponse](models.md#importaddonresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.ImportAddonRequest` | `REQUIRED` |

---


## `addon.list_available_addons`
```python
await self.api.addon.list_available_addons(request: bedrock_server_manager.api.models.addon.ListAvailableAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists available .mcaddon and .mcpack files from the content directory.

- **Returns:** `ListAvailableAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListAvailableAddonsRequest
payload = {}
request = ListAvailableAddonsRequest(**payload)
result = await self.api.addon.list_available_addons(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ListAvailableAddonsRequest](models.md#listavailableaddonsrequest)
- **Response schema:** [ListAvailableAddonsResponse](models.md#listavailableaddonsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.ListAvailableAddonsRequest` | `REQUIRED` |

---


## `addon.list_installed_addons`
```python
await self.api.addon.list_installed_addons(request: bedrock_server_manager.api.models.addon.ListInstalledAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists all addons for a server's active world.

- **Returns:** `ListInstalledAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListInstalledAddonsRequest
payload = {'server_name': 'example'}
request = ListInstalledAddonsRequest(**payload)
result = await self.api.addon.list_installed_addons(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ListInstalledAddonsRequest](models.md#listinstalledaddonsrequest)
- **Response schema:** [ListInstalledAddonsResponse](models.md#listinstalledaddonsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.ListInstalledAddonsRequest` | `REQUIRED` |

---


## `addon.reorder_addons`
```python
await self.api.addon.reorder_addons(request: bedrock_server_manager.api.models.addon.ReorderAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reorder the active addons for a server's active world.

- **Returns:** `ReorderAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ReorderAddonsRequest
payload = {...}  # Supply required request fields below.
request = ReorderAddonsRequest(**payload)
result = await self.api.addon.reorder_addons(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ReorderAddonsRequest](models.md#reorderaddonsrequest)
- **Response schema:** [ReorderAddonsResponse](models.md#reorderaddonsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.ReorderAddonsRequest` | `REQUIRED` |
