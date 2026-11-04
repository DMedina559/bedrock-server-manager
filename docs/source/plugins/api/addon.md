# Addon plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `addon.disable_addon`
```python
await self.api.addon.disable_addon(request: bedrock_server_manager.models.addon.DisableAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Disables an active addon for a server's active world, preserving files.

- **Required Permission:** `addons:manage`

- **Returns:** `DisableAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import DisableAddonRequest
request = DisableAddonRequest(pack_uuid=..., pack_type=..., server_name='example')
result = await self.api.addon.disable_addon(request)
```
- **Request schema:** [DisableAddonRequest](models.md#disableaddonrequest)
- **Response schema:** [DisableAddonResponse](models.md#disableaddonresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.addon.DisableAddonRequest` | `REQUIRED` |

---


## `addon.enable_addon`
```python
await self.api.addon.enable_addon(request: bedrock_server_manager.models.addon.EnableAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Enables a disabled addon for a server's active world.

- **Required Permission:** `addons:manage`

- **Returns:** `EnableAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import EnableAddonRequest
request = EnableAddonRequest(pack_uuid=..., pack_type=..., server_name='example')
result = await self.api.addon.enable_addon(request)
```
- **Request schema:** [EnableAddonRequest](models.md#enableaddonrequest)
- **Response schema:** [EnableAddonResponse](models.md#enableaddonresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.addon.EnableAddonRequest` | `REQUIRED` |

---


## `addon.import_addon`
```python
await self.api.addon.import_addon(request: bedrock_server_manager.models.addon.ImportAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Installs an addon to a specified Bedrock server.

- **Required Permission:** `addons:manage`

- **Returns:** `ImportAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ImportAddonRequest
request = ImportAddonRequest(server_name='example', addon_file_path=...)
result = await self.api.addon.import_addon(request)
```
- **Request schema:** [ImportAddonRequest](models.md#importaddonrequest)
- **Response schema:** [ImportAddonResponse](models.md#importaddonresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.addon.ImportAddonRequest` | `REQUIRED` |

---


## `addon.list_available_addons`
```python
await self.api.addon.list_available_addons(request: bedrock_server_manager.models.addon.ListAvailableAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists available .mcaddon and .mcpack files from the content directory.

- **Required Permission:** `content:read`

- **Returns:** `ListAvailableAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListAvailableAddonsRequest
request = ListAvailableAddonsRequest()
result = await self.api.addon.list_available_addons(request)
```
- **Request schema:** [ListAvailableAddonsRequest](models.md#listavailableaddonsrequest)
- **Response schema:** [ListAvailableAddonsResponse](models.md#listavailableaddonsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.addon.ListAvailableAddonsRequest` | `REQUIRED` |

---


## `addon.list_installed_addons`
```python
await self.api.addon.list_installed_addons(request: bedrock_server_manager.models.addon.ListInstalledAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists all addons for a server's active world.

- **Required Permission:** `addons:read`

- **Returns:** `ListInstalledAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListInstalledAddonsRequest
request = ListInstalledAddonsRequest(server_name='example')
result = await self.api.addon.list_installed_addons(request)
```
- **Request schema:** [ListInstalledAddonsRequest](models.md#listinstalledaddonsrequest)
- **Response schema:** [ListInstalledAddonsResponse](models.md#listinstalledaddonsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.addon.ListInstalledAddonsRequest` | `REQUIRED` |

---


## `addon.reorder_addons`
```python
await self.api.addon.reorder_addons(request: bedrock_server_manager.models.addon.ReorderAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reorder the active addons for a server's active world.

- **Required Permission:** `addons:manage`

- **Returns:** `ReorderAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ReorderAddonsRequest
request = ReorderAddonsRequest(pack_type=..., uuids=..., server_name='example')
result = await self.api.addon.reorder_addons(request)
```
- **Request schema:** [ReorderAddonsRequest](models.md#reorderaddonsrequest)
- **Response schema:** [ReorderAddonsResponse](models.md#reorderaddonsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.addon.ReorderAddonsRequest` | `REQUIRED` |

---


## `addon.update_subpack`
```python
await self.api.addon.update_subpack(request: bedrock_server_manager.models.addon.UpdateSubpackRequest)
```
- **Async (Requires await):** Yes

- **Description:** Updates the active subpack for an addon on a server's active world.

- **Required Permission:** `addons:manage`

- **Returns:** `UpdateSubpackResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import UpdateSubpackRequest
request = UpdateSubpackRequest(pack_uuid=..., pack_type=..., subpack_name=..., server_name='example')
result = await self.api.addon.update_subpack(request)
```
- **Request schema:** [UpdateSubpackRequest](models.md#updatesubpackrequest)
- **Response schema:** [UpdateSubpackResponse](models.md#updatesubpackresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.addon.UpdateSubpackRequest` | `REQUIRED` |
