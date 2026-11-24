# Misc plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `misc.prune_download_cache`
```python
await self.api.misc.prune_download_cache(request: bedrock_server_manager.models.misc.PruneDownloadCacheRequest)
```
- **Async (Requires await):** Yes

- **Description:** Prunes old downloaded server archives (.zip) in a directory.

- **Required Permission:** `downloads:prune`

- **Returns:** `PruneDownloadCacheResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import PruneDownloadCacheRequest
request = PruneDownloadCacheRequest(download_dir=...)
result = await self.api.misc.prune_download_cache(request)
```
- **Request schema:** [PruneDownloadCacheRequest](models.md#prunedownloadcacherequest)
- **Response schema:** [PruneDownloadCacheResponse](models.md#prunedownloadcacheresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.misc.PruneDownloadCacheRequest` | `REQUIRED` |
