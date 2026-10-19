# Backup Restore plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `backup_restore.backup_all`
```python
await self.api.backup_restore.backup_all(request: bedrock_server_manager.api.models.backup_restore.BackupAllRequest)
```
- **Async (Requires await):** Yes

- **Description:** Performs a full backup of the server's world and configuration files.

- **Returns:** `BackupAllResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import BackupAllRequest
payload = {'server_name': 'example'}
request = BackupAllRequest(**payload)
result = await self.api.backup_restore.backup_all(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [BackupAllRequest](models.md#backupallrequest)
- **Response schema:** [BackupAllResponse](models.md#backupallresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.BackupAllRequest` | `REQUIRED` |

---


## `backup_restore.backup_config_file`
```python
await self.api.backup_restore.backup_config_file(request: bedrock_server_manager.api.models.backup_restore.BackupConfigFileRequest)
```
- **Async (Requires await):** Yes

- **Description:** Create a backup of a specific server configuration file.

- **Returns:** `BackupConfigFileResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import BackupConfigFileRequest
payload = {...}  # Supply required request fields below.
request = BackupConfigFileRequest(**payload)
result = await self.api.backup_restore.backup_config_file(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [BackupConfigFileRequest](models.md#backupconfigfilerequest)
- **Response schema:** [BackupConfigFileResponse](models.md#backupconfigfileresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.BackupConfigFileRequest` | `REQUIRED` |

---


## `backup_restore.backup_world`
```python
await self.api.backup_restore.backup_world(request: bedrock_server_manager.api.models.backup_restore.BackupWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Create a backup of the server's world directory.

- **Returns:** `BackupWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import BackupWorldRequest
payload = {'server_name': 'example'}
request = BackupWorldRequest(**payload)
result = await self.api.backup_restore.backup_world(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [BackupWorldRequest](models.md#backupworldrequest)
- **Response schema:** [BackupWorldResponse](models.md#backupworldresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.BackupWorldRequest` | `REQUIRED` |

---


## `backup_restore.create_server_backup`
```python
await self.api.backup_restore.create_server_backup(request: bedrock_server_manager.api.models.backup_restore.CreateSnapshotRequest)
```
- **Async (Requires await):** Yes

- **Description:** Capture one coherent, optionally encrypted server archive.

- **Returns:** `CreateSnapshotResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import CreateSnapshotRequest
payload = {'server_name': 'example'}
request = CreateSnapshotRequest(**payload)
result = await self.api.backup_restore.create_server_backup(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [CreateSnapshotRequest](models.md#createsnapshotrequest)
- **Response schema:** [CreateSnapshotResponse](models.md#createsnapshotresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.CreateSnapshotRequest` | `REQUIRED` |

---


## `backup_restore.get_restore_recovery`
```python
await self.api.backup_restore.get_restore_recovery(request: bedrock_server_manager.api.models.backup_restore.ListSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Inspect recovery state without exposing journal files or secret settings.

- **Returns:** `RestoreRecoveryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListSnapshotsRequest
payload = {'server_name': 'example'}
request = ListSnapshotsRequest(**payload)
result = await self.api.backup_restore.get_restore_recovery(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ListSnapshotsRequest](models.md#listsnapshotsrequest)
- **Response schema:** [RestoreRecoveryResponse](models.md#restorerecoveryresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.ListSnapshotsRequest` | `REQUIRED` |

---


## `backup_restore.inspect_server_backup`
```python
await self.api.backup_restore.inspect_server_backup(request: bedrock_server_manager.api.models.backup_restore.InspectSnapshotRequest)
```
- **Async (Requires await):** Yes

- **Description:** Authenticate a backup and return its manifest without secret file values.

- **Returns:** `InspectSnapshotResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import InspectSnapshotRequest
payload = {...}  # Supply required request fields below.
request = InspectSnapshotRequest(**payload)
result = await self.api.backup_restore.inspect_server_backup(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [InspectSnapshotRequest](models.md#inspectsnapshotrequest)
- **Response schema:** [InspectSnapshotResponse](models.md#inspectsnapshotresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.InspectSnapshotRequest` | `REQUIRED` |

---


## `backup_restore.list_backup_files`
```python
await self.api.backup_restore.list_backup_files(request: bedrock_server_manager.api.models.backup_restore.ListBackupFilesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists available backup files for a given server and type.

- **Returns:** `ListBackupFilesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListBackupFilesRequest
payload = {...}  # Supply required request fields below.
request = ListBackupFilesRequest(**payload)
result = await self.api.backup_restore.list_backup_files(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ListBackupFilesRequest](models.md#listbackupfilesrequest)
- **Response schema:** [ListBackupFilesResponse](models.md#listbackupfilesresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.ListBackupFilesRequest` | `REQUIRED` |

---


## `backup_restore.list_server_snapshots`
```python
await self.api.backup_restore.list_server_snapshots(request: bedrock_server_manager.api.models.backup_restore.ListSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** List portable archives without decrypting their private manifests.

- **Returns:** `ListSnapshotsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListSnapshotsRequest
payload = {'server_name': 'example'}
request = ListSnapshotsRequest(**payload)
result = await self.api.backup_restore.list_server_snapshots(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ListSnapshotsRequest](models.md#listsnapshotsrequest)
- **Response schema:** [ListSnapshotsResponse](models.md#listsnapshotsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.ListSnapshotsRequest` | `REQUIRED` |

---


## `backup_restore.plan_server_restore`
```python
await self.api.backup_restore.plan_server_restore(request: bedrock_server_manager.api.models.backup_restore.PlanSnapshotRestoreRequest)
```
- **Async (Requires await):** Yes

- **Description:** Validate selected contents and bind a restore plan to current destinations.

- **Returns:** `PlanSnapshotRestoreResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import PlanSnapshotRestoreRequest
payload = {...}  # Supply required request fields below.
request = PlanSnapshotRestoreRequest(**payload)
result = await self.api.backup_restore.plan_server_restore(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [PlanSnapshotRestoreRequest](models.md#plansnapshotrestorerequest)
- **Response schema:** [PlanSnapshotRestoreResponse](models.md#plansnapshotrestoreresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.PlanSnapshotRestoreRequest` | `REQUIRED` |

---


## `backup_restore.prune_old_backups`
```python
await self.api.backup_restore.prune_old_backups(request: bedrock_server_manager.api.models.backup_restore.PruneOldBackupsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Prunes old backups for a server based on retention settings.

- **Returns:** `PruneOldBackupsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import PruneOldBackupsRequest
payload = {'server_name': 'example'}
request = PruneOldBackupsRequest(**payload)
result = await self.api.backup_restore.prune_old_backups(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [PruneOldBackupsRequest](models.md#pruneoldbackupsrequest)
- **Response schema:** [PruneOldBackupsResponse](models.md#pruneoldbackupsresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.PruneOldBackupsRequest` | `REQUIRED` |

---


## `backup_restore.recover_server_backup`
```python
await self.api.backup_restore.recover_server_backup(request: bedrock_server_manager.api.models.backup_restore.ListSnapshotsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Retry an interrupted restore's recovery while preserving its journal on failure.

- **Returns:** `RestoreRecoveryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListSnapshotsRequest
payload = {'server_name': 'example'}
request = ListSnapshotsRequest(**payload)
result = await self.api.backup_restore.recover_server_backup(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [ListSnapshotsRequest](models.md#listsnapshotsrequest)
- **Response schema:** [RestoreRecoveryResponse](models.md#restorerecoveryresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.ListSnapshotsRequest` | `REQUIRED` |

---


## `backup_restore.restore_all`
```python
await self.api.backup_restore.restore_all(request: bedrock_server_manager.api.models.backup_restore.RestoreAllRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores the server from the latest available backups.

- **Returns:** `RestoreAllResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestoreAllRequest
payload = {'server_name': 'example'}
request = RestoreAllRequest(**payload)
result = await self.api.backup_restore.restore_all(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [RestoreAllRequest](models.md#restoreallrequest)
- **Response schema:** [RestoreAllResponse](models.md#restoreallresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.RestoreAllRequest` | `REQUIRED` |

---


## `backup_restore.restore_config_file`
```python
await self.api.backup_restore.restore_config_file(request: bedrock_server_manager.api.models.backup_restore.RestoreConfigFileRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores a specific config file from a backup.

- **Returns:** `RestoreConfigFileResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestoreConfigFileRequest
payload = {...}  # Supply required request fields below.
request = RestoreConfigFileRequest(**payload)
result = await self.api.backup_restore.restore_config_file(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [RestoreConfigFileRequest](models.md#restoreconfigfilerequest)
- **Response schema:** [RestoreConfigFileResponse](models.md#restoreconfigfileresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.RestoreConfigFileRequest` | `REQUIRED` |

---


## `backup_restore.restore_server_snapshot`
```python
await self.api.backup_restore.restore_server_snapshot(request: bedrock_server_manager.api.models.backup_restore.RestoreSnapshotRequest)
```
- **Async (Requires await):** Yes

- **Description:** Apply a reviewed restore and keep restart failures separate from data recovery.

- **Returns:** `RestoreSnapshotResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestoreSnapshotRequest
payload = {...}  # Supply required request fields below.
request = RestoreSnapshotRequest(**payload)
result = await self.api.backup_restore.restore_server_snapshot(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [RestoreSnapshotRequest](models.md#restoresnapshotrequest)
- **Response schema:** [RestoreSnapshotResponse](models.md#restoresnapshotresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.RestoreSnapshotRequest` | `REQUIRED` |

---


## `backup_restore.restore_world`
```python
await self.api.backup_restore.restore_world(request: bedrock_server_manager.api.models.backup_restore.RestoreWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores a server's world from a specific backup file.

- **Returns:** `RestoreWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestoreWorldRequest
payload = {...}  # Supply required request fields below.
request = RestoreWorldRequest(**payload)
result = await self.api.backup_restore.restore_world(request)
data = result.model_dump(mode="json")
```
- **Request schema:** [RestoreWorldRequest](models.md#restoreworldrequest)
- **Response schema:** [RestoreWorldResponse](models.md#restoreworldresponse)
- **Transport error schema:** [APIErrorResponse](models.md#apierrorresponse)
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.RestoreWorldRequest` | `REQUIRED` |
