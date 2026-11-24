# Backup Restore plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `backup_restore.can_reuse_server_backup`
```python
await self.api.backup_restore.can_reuse_server_backup(request: bedrock_server_manager.models.backup_restore.SnapshotReuseRequest)
```
- **Async (Requires await):** Yes

- **Description:** Check coverage and availability without exposing archive paths or file values.

- **Required Permission:** `backups:read`

- **Returns:** `SnapshotReuseResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import SnapshotReuseRequest
request = SnapshotReuseRequest(server_name='example')
result = await self.api.backup_restore.can_reuse_server_backup(request)
```
- **Request schema:** [SnapshotReuseRequest](models.md#snapshotreuserequest)
- **Response schema:** [SnapshotReuseResponse](models.md#snapshotreuseresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.SnapshotReuseRequest` | `REQUIRED` |

---


## `backup_restore.create_server_backup`
```python
await self.api.backup_restore.create_server_backup(request: bedrock_server_manager.models.backup_restore.CreateSnapshotRequest)
```
- **Async (Requires await):** Yes

- **Description:** Capture one coherent, optionally encrypted server archive.

- **Required Permission:** `backups:create`

- **Returns:** `CreateSnapshotResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import CreateSnapshotRequest
request = CreateSnapshotRequest(server_name='example')
result = await self.api.backup_restore.create_server_backup(request)
```
- **Request schema:** [CreateSnapshotRequest](models.md#createsnapshotrequest)
- **Response schema:** [CreateSnapshotResponse](models.md#createsnapshotresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.CreateSnapshotRequest` | `REQUIRED` |

---


## `backup_restore.download_backup_recovery_report`
```python
await self.api.backup_restore.download_backup_recovery_report(request: bedrock_server_manager.models.backup_restore.ListSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Export allowlisted recovery evidence without file paths or secret values.

- **Required Permission:** `backups:read`

- **Returns:** `RecoveryReportResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListSnapshotsRequest
request = ListSnapshotsRequest(server_name='example')
result = await self.api.backup_restore.download_backup_recovery_report(request)
```
- **Request schema:** [ListSnapshotsRequest](models.md#listsnapshotsrequest)
- **Response schema:** [RecoveryReportResponse](models.md#recoveryreportresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.ListSnapshotsRequest` | `REQUIRED` |

---


## `backup_restore.dry_run_server_restore`
```python
await self.api.backup_restore.dry_run_server_restore(request: bedrock_server_manager.models.backup_restore.PlanSnapshotRestoreRequest)
```
- **Async (Requires await):** Yes

- **Description:** Validate and copy selected contents in isolation without stopping Minecraft.

- **Required Permission:** `backups:restore`

- **Returns:** `PlanSnapshotRestoreResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import PlanSnapshotRestoreRequest
request = PlanSnapshotRestoreRequest(server_name='example', backup_id=..., components=...)
result = await self.api.backup_restore.dry_run_server_restore(request)
```
- **Request schema:** [PlanSnapshotRestoreRequest](models.md#plansnapshotrestorerequest)
- **Response schema:** [PlanSnapshotRestoreResponse](models.md#plansnapshotrestoreresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.PlanSnapshotRestoreRequest` | `REQUIRED` |

---


## `backup_restore.get_backup_health`
```python
await self.api.backup_restore.get_backup_health(request: bedrock_server_manager.models.backup_restore.ListSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Report durable backup health without opening secret archive contents.

- **Required Permission:** `backups:read`

- **Returns:** `BackupHealthResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListSnapshotsRequest
request = ListSnapshotsRequest(server_name='example')
result = await self.api.backup_restore.get_backup_health(request)
```
- **Request schema:** [ListSnapshotsRequest](models.md#listsnapshotsrequest)
- **Response schema:** [BackupHealthResponse](models.md#backuphealthresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.ListSnapshotsRequest` | `REQUIRED` |

---


## `backup_restore.get_restore_recovery`
```python
await self.api.backup_restore.get_restore_recovery(request: bedrock_server_manager.models.backup_restore.ListSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Inspect recovery state without exposing journal files or secret settings.

- **Required Permission:** `backups:read`

- **Returns:** `RestoreRecoveryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListSnapshotsRequest
request = ListSnapshotsRequest(server_name='example')
result = await self.api.backup_restore.get_restore_recovery(request)
```
- **Request schema:** [ListSnapshotsRequest](models.md#listsnapshotsrequest)
- **Response schema:** [RestoreRecoveryResponse](models.md#restorerecoveryresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.ListSnapshotsRequest` | `REQUIRED` |

---


## `backup_restore.inspect_server_backup`
```python
await self.api.backup_restore.inspect_server_backup(request: bedrock_server_manager.models.backup_restore.InspectSnapshotRequest)
```
- **Async (Requires await):** Yes

- **Description:** Authenticate a backup and return its manifest without secret file values.

- **Required Permission:** `backups:read`

- **Returns:** `InspectSnapshotResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import InspectSnapshotRequest
request = InspectSnapshotRequest(server_name='example', backup_id=...)
result = await self.api.backup_restore.inspect_server_backup(request)
```
- **Request schema:** [InspectSnapshotRequest](models.md#inspectsnapshotrequest)
- **Response schema:** [InspectSnapshotResponse](models.md#inspectsnapshotresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.InspectSnapshotRequest` | `REQUIRED` |

---


## `backup_restore.list_backup_files`
```python
await self.api.backup_restore.list_backup_files(request: bedrock_server_manager.models.backup_restore.ListBackupFilesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists available backup files for a given server and type.

- **Required Permission:** `backups:read`

- **Returns:** `ListBackupFilesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListBackupFilesRequest
request = ListBackupFilesRequest(server_name='example', backup_type=...)
result = await self.api.backup_restore.list_backup_files(request)
```
- **Request schema:** [ListBackupFilesRequest](models.md#listbackupfilesrequest)
- **Response schema:** [ListBackupFilesResponse](models.md#listbackupfilesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.ListBackupFilesRequest` | `REQUIRED` |

---


## `backup_restore.list_server_snapshots`
```python
await self.api.backup_restore.list_server_snapshots(request: bedrock_server_manager.models.backup_restore.ListSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** List portable archives without decrypting their private manifests.

- **Required Permission:** `backups:read`

- **Returns:** `ListSnapshotsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListSnapshotsRequest
request = ListSnapshotsRequest(server_name='example')
result = await self.api.backup_restore.list_server_snapshots(request)
```
- **Request schema:** [ListSnapshotsRequest](models.md#listsnapshotsrequest)
- **Response schema:** [ListSnapshotsResponse](models.md#listsnapshotsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.ListSnapshotsRequest` | `REQUIRED` |

---


## `backup_restore.manage_server_snapshot`
```python
await self.api.backup_restore.manage_server_snapshot(request: bedrock_server_manager.models.backup_restore.ManageSnapshotRequest)
```
- **Async (Requires await):** Yes

- **Description:** Verify, pin, copy, or test a recovery key against an authenticated archive.

- **Required Permission:** `backups:manage`

- **Returns:** `ManageSnapshotResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ManageSnapshotRequest
request = ManageSnapshotRequest(server_name='example', backup_id=..., action=...)
result = await self.api.backup_restore.manage_server_snapshot(request)
```
- **Request schema:** [ManageSnapshotRequest](models.md#managesnapshotrequest)
- **Response schema:** [ManageSnapshotResponse](models.md#managesnapshotresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.ManageSnapshotRequest` | `REQUIRED` |

---


## `backup_restore.plan_server_restore`
```python
await self.api.backup_restore.plan_server_restore(request: bedrock_server_manager.models.backup_restore.PlanSnapshotRestoreRequest)
```
- **Async (Requires await):** Yes

- **Description:** Validate selected contents and bind a restore plan to current destinations.

- **Required Permission:** `backups:restore`

- **Returns:** `PlanSnapshotRestoreResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import PlanSnapshotRestoreRequest
request = PlanSnapshotRestoreRequest(server_name='example', backup_id=..., components=...)
result = await self.api.backup_restore.plan_server_restore(request)
```
- **Request schema:** [PlanSnapshotRestoreRequest](models.md#plansnapshotrestorerequest)
- **Response schema:** [PlanSnapshotRestoreResponse](models.md#plansnapshotrestoreresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.PlanSnapshotRestoreRequest` | `REQUIRED` |

---


## `backup_restore.prune_old_backups`
```python
await self.api.backup_restore.prune_old_backups(request: bedrock_server_manager.models.backup_restore.PruneOldBackupsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Prunes old backups for a server based on retention settings.

- **Required Permission:** `backups:prune`

- **Returns:** `PruneOldBackupsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import PruneOldBackupsRequest
request = PruneOldBackupsRequest(server_name='example')
result = await self.api.backup_restore.prune_old_backups(request)
```
- **Request schema:** [PruneOldBackupsRequest](models.md#pruneoldbackupsrequest)
- **Response schema:** [PruneOldBackupsResponse](models.md#pruneoldbackupsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.PruneOldBackupsRequest` | `REQUIRED` |

---


## `backup_restore.recover_server_backup`
```python
await self.api.backup_restore.recover_server_backup(request: bedrock_server_manager.models.backup_restore.ListSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Retry an interrupted restore's recovery while preserving its journal on failure.

- **Required Permission:** `backups:restore`

- **Returns:** `RestoreRecoveryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import ListSnapshotsRequest
request = ListSnapshotsRequest(server_name='example')
result = await self.api.backup_restore.recover_server_backup(request)
```
- **Request schema:** [ListSnapshotsRequest](models.md#listsnapshotsrequest)
- **Response schema:** [RestoreRecoveryResponse](models.md#restorerecoveryresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.ListSnapshotsRequest` | `REQUIRED` |

---


## `backup_restore.restore_all`
```python
await self.api.backup_restore.restore_all(request: bedrock_server_manager.models.backup_restore.RestoreAllRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores the server from the latest available backups.

- **Required Permission:** `backups:restore`

- **Returns:** `RestoreAllResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import RestoreAllRequest
request = RestoreAllRequest(server_name='example')
result = await self.api.backup_restore.restore_all(request)
```
- **Request schema:** [RestoreAllRequest](models.md#restoreallrequest)
- **Response schema:** [RestoreAllResponse](models.md#restoreallresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.RestoreAllRequest` | `REQUIRED` |

---


## `backup_restore.restore_config_file`
```python
await self.api.backup_restore.restore_config_file(request: bedrock_server_manager.models.backup_restore.RestoreConfigFileRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores a specific config file from a backup.

- **Required Permission:** `backups:restore`

- **Returns:** `RestoreConfigFileResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import RestoreConfigFileRequest
request = RestoreConfigFileRequest(server_name='example', backup_file_path=...)
result = await self.api.backup_restore.restore_config_file(request)
```
- **Request schema:** [RestoreConfigFileRequest](models.md#restoreconfigfilerequest)
- **Response schema:** [RestoreConfigFileResponse](models.md#restoreconfigfileresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.RestoreConfigFileRequest` | `REQUIRED` |

---


## `backup_restore.restore_server_snapshot`
```python
await self.api.backup_restore.restore_server_snapshot(request: bedrock_server_manager.models.backup_restore.RestoreSnapshotRequest)
```
- **Async (Requires await):** Yes

- **Description:** Apply a reviewed restore and keep restart failures separate from data recovery.

- **Required Permission:** `backups:restore`

- **Returns:** `RestoreSnapshotResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import RestoreSnapshotRequest
request = RestoreSnapshotRequest(server_name='example', backup_id=..., components=..., token=...)
result = await self.api.backup_restore.restore_server_snapshot(request)
```
- **Request schema:** [RestoreSnapshotRequest](models.md#restoresnapshotrequest)
- **Response schema:** [RestoreSnapshotResponse](models.md#restoresnapshotresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.RestoreSnapshotRequest` | `REQUIRED` |

---


## `backup_restore.restore_world`
```python
await self.api.backup_restore.restore_world(request: bedrock_server_manager.models.backup_restore.RestoreWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores a server's world from a specific backup file.

- **Required Permission:** `backups:restore`

- **Returns:** `RestoreWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.models import RestoreWorldRequest
request = RestoreWorldRequest(server_name='example', backup_file_path=...)
result = await self.api.backup_restore.restore_world(request)
```
- **Request schema:** [RestoreWorldRequest](models.md#restoreworldrequest)
- **Response schema:** [RestoreWorldResponse](models.md#restoreworldresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.models.backup_restore.RestoreWorldRequest` | `REQUIRED` |
