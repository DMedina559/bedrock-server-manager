# Available plugin events

> _Generated from registered core contracts._

---
This list contains all core application events available to plugins.
You can listen to these events using the `@app_event("event_name")` decorator.
If an event is **Cancellable**, you can access `kwargs['event']` (which is a `CancellableEvent` object) and call `event.cancel(reason)` to halt the core operation.

## `after_add_server_ban`
**Description:** Triggered after 'add_server_ban'. Adds a player to the server ban list.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, xuid`

### Listener Signature:
```python
@app_event("after_add_server_ban")
async def some_function(self, request, server_name, player_name, xuid, reason, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `AddServerBanRequest` |
| `server_name` | `str` |
| `player_name` | `str` |
| `xuid` | `str` |
| `reason` | `str | None` |
| `result` | `AddServerBanResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_addon_disable`
**Description:** Triggered after 'disable_addon'. Disables an active addon for a server's active world, preserving files.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, pack_uuid`

### Listener Signature:
```python
@app_event("after_addon_disable")
async def some_function(self, request, server_name, pack_uuid, pack_type, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `DisableAddonRequest` |
| `server_name` | `str` |
| `pack_uuid` | `str` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `result` | `DisableAddonResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_addon_enable`
**Description:** Triggered after 'enable_addon'. Enables a disabled addon for a server's active world.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, pack_uuid`

### Listener Signature:
```python
@app_event("after_addon_enable")
async def some_function(self, request, server_name, pack_uuid, pack_type, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `EnableAddonRequest` |
| `server_name` | `str` |
| `pack_uuid` | `str` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `result` | `EnableAddonResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_addon_import`
**Description:** Triggered after 'import_addon'. Installs an addon to a specified Bedrock server.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, addon_file_path`

### Listener Signature:
```python
@app_event("after_addon_import")
async def some_function(self, request, server_name, addon_file_path, stop_start_server, restart_only_on_success, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ImportAddonRequest` |
| `server_name` | `str` |
| `addon_file_path` | `str` |
| `stop_start_server` | `bool` |
| `restart_only_on_success` | `bool` |
| `result` | `ImportAddonResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_addon_reorder`
**Description:** Triggered after 'reorder_addons'. Reorder the active addons for a server's active world.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_addon_reorder")
async def some_function(self, request, server_name, uuids, pack_type, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ReorderAddonsRequest` |
| `server_name` | `str` |
| `uuids` | `list[str]` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `result` | `ReorderAddonsResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_addon_subpack_update`
**Description:** Triggered after 'update_subpack'. Updates the active subpack for an addon on a server's active world.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, pack_uuid`

### Listener Signature:
```python
@app_event("after_addon_subpack_update")
async def some_function(self, request, server_name, pack_uuid, pack_type, subpack_name, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `UpdateSubpackRequest` |
| `server_name` | `str` |
| `pack_uuid` | `str` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `subpack_name` | `str` |
| `result` | `UpdateSubpackResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_addon_uninstall`
**Description:** Triggered after 'uninstall_addon'. Uninstalls an addon for a server's active world, deleting its files.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, pack_uuid`

### Listener Signature:
```python
@app_event("after_addon_uninstall")
async def some_function(self, request, server_name, pack_uuid, pack_type, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `UninstallAddonRequest` |
| `server_name` | `str` |
| `pack_uuid` | `str` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `result` | `UninstallAddonResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_allowlist_change`
**Description:** Triggered after 'remove_from_allowlist'. Remove a list of players from the server's allowlist.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_allowlist_change")
async def some_function(self, *, request, server_name, new_players_data=None, result, player_names=None, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `AddToAllowlistRequest | RemoveFromAllowlistRequest` |
| `server_name` | `str` |
| `new_players_data` | `list[bedrock_server_manager.api.models.allowlist.AllowlistPlayer]` |
| `result` | `AddToAllowlistResponse | RemoveFromAllowlistResponse` |
| `player_names` | `list[str]` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_backup`
**Description:** Triggered after 'create_server_backup'. Capture one coherent, optionally encrypted server archive.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_backup")
async def some_function(self, *, request, server_name, result, file_to_backup=None, encrypted=None, include_packs=None, purpose=None, schedule_slot=None, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `BackupWorldRequest | BackupConfigFileRequest | BackupAllRequest | CreateSnapshotRequest` |
| `server_name` | `str` |
| `result` | `BackupWorldResponse | BackupConfigFileResponse | BackupAllResponse | CreateSnapshotResponse` |
| `file_to_backup` | `str` |
| `encrypted` | `bool | None` |
| `include_packs` | `bool | None` |
| `purpose` | `Literal['manual', 'scheduled']` |
| `schedule_slot` | `str | None` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_command_send`
**Description:** Triggered after 'send_command'. Sends a command to a running Bedrock server.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, command`

### Listener Signature:
```python
@app_event("after_command_send")
async def some_function(self, request, server_name, command, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SendCommandRequest` |
| `server_name` | `str` |
| `command` | `str` |
| `result` | `SendCommandResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_delete_server_data`
**Description:** Triggered after 'delete_server_data'. Delete all data associated with a Bedrock server.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_delete_server_data")
async def some_function(self, request, server_name, stop_if_running, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `DeleteServerDataRequest` |
| `server_name` | `str` |
| `stop_if_running` | `bool` |
| `result` | `DeleteServerDataResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_permission_change`
**Description:** Triggered after 'set_permissions'. Set a player's permission level for a given server.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, xuid`

### Listener Signature:
```python
@app_event("after_permission_change")
async def some_function(self, request, server_name, xuid, player_name, permission, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetPermissionsRequest` |
| `server_name` | `str` |
| `xuid` | `str` |
| `player_name` | `str | None` |
| `permission` | `Literal['visitor', 'member', 'operator']` |
| `result` | `SetPermissionsResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_player_db_scan`
**Description:** Triggered after 'scan_and_update_player_db'. Scans all server logs to discover and save player data.
- **Cancellable:** No

### Listener Signature:
```python
@app_event("after_player_db_scan")
async def some_function(self, request, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ScanAndUpdatePlayerDbRequest` |
| `result` | `ScanAndUpdatePlayerDbResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_players_add`
**Description:** Triggered after 'add_players_manually'. Adds or updates player data in the database.
- **Cancellable:** No

### Listener Signature:
```python
@app_event("after_players_add")
async def some_function(self, request, player_strings, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `AddPlayersManuallyRequest` |
| `player_strings` | `list[str]` |
| `result` | `AddPlayersManuallyResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_plugin_settings_update`
**Description:** Triggered after 'update_plugin_settings'. No description.
- **Cancellable:** No

### Listener Signature:
```python
@app_event("after_plugin_settings_update")
async def some_function(self, *, request, key=None, value=None, result, plugin_name=None, settings=None, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetPluginSettingRequest | UpdatePluginSettingsRequest` |
| `key` | `str` |
| `value` | `JsonValue` |
| `result` | `SetPluginSettingResponse` |
| `plugin_name` | `str` |
| `settings` | `dict[str, JsonValue]` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_properties_change`
**Description:** Triggered after 'set_properties'. Set one or multiple server properties for a given server.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_properties_change")
async def some_function(self, request, server_name, properties_to_update, restart_after_modify, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetPropertiesRequest` |
| `server_name` | `str` |
| `properties_to_update` | `dict[str, str]` |
| `restart_after_modify` | `bool` |
| `result` | `SetPropertiesResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_prune_backups`
**Description:** Triggered after 'prune_old_backups'. Prunes old backups for a server based on retention settings.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_prune_backups")
async def some_function(self, request, server_name, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `PruneOldBackupsRequest` |
| `server_name` | `str` |
| `result` | `PruneOldBackupsResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_prune_download_cache`
**Description:** Triggered after 'prune_download_cache'. Prunes old downloaded server archives (.zip) in a directory.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `download_dir, keep_count`

### Listener Signature:
```python
@app_event("after_prune_download_cache")
async def some_function(self, request, download_dir, keep_count, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `PruneDownloadCacheRequest` |
| `download_dir` | `str` |
| `keep_count` | `int | None` |
| `result` | `PruneDownloadCacheResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_remove_server_ban`
**Description:** Triggered after 'remove_server_ban'. Remove a player from the server ban list.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, xuid`

### Listener Signature:
```python
@app_event("after_remove_server_ban")
async def some_function(self, request, server_name, xuid, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `RemoveServerBanRequest` |
| `server_name` | `str` |
| `xuid` | `str` |
| `result` | `RemoveServerBanResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_restore`
**Description:** Triggered after 'recover_server_backup'. Retry an interrupted restore's recovery while preserving its journal on failure.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_restore")
async def some_function(self, *, request, server_name, stop_start_server=None, result, backup_file_path=None, component=None, backup_id=None, components=None, token=None, restart=None, stop_running=None, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `RestoreAllRequest | RestoreWorldRequest | RestoreConfigFileRequest | RestoreSnapshotRequest | ListSnapshotsRequest` |
| `server_name` | `str` |
| `stop_start_server` | `bool` |
| `result` | `RestoreAllResponse | RestoreWorldResponse | RestoreConfigFileResponse | RestoreSnapshotResponse | RestoreRecoveryResponse` |
| `backup_file_path` | `str` |
| `component` | `Literal['server.properties', 'allowlist.json', 'permissions.json'] | None` |
| `backup_id` | `str` |
| `components` | `list[Literal['server_directory', 'world', 'server.properties', 'allowlist.json', 'permissions.json', 'script_config', 'bsm_settings', 'behavior_packs', 'resource_packs', 'development_behavior_packs', 'development_resource_packs']]` |
| `token` | `str` |
| `restart` | `bool` |
| `stop_running` | `bool` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_server_install`
**Description:** Triggered after 'install_new_server'. Installs a new server instance.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, target_version`

### Listener Signature:
```python
@app_event("after_server_install")
async def some_function(self, request, server_name, target_version, server_zip_path, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `InstallNewServerRequest` |
| `server_name` | `str` |
| `target_version` | `str` |
| `server_zip_path` | `str | None` |
| `result` | `InstallNewServerResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_server_players_change`
**Description:** Triggered after 'update_server_player_stats'. Internal API to trigger player stat updates for websockets/plugins.
- **Cancellable:** No

### Listener Signature:
```python
@app_event("after_server_players_change")
async def some_function(self, server_name, player_count, players, request, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `server_name` | `str` |
| `player_count` | `int` |
| `players` | `list[bedrock_server_manager.events.player.PlayerPresence] | list[bedrock_server_manager.api.models.common.PlayerInfo]` |
| `request` | `PlayerSnapshot | UpdateServerPlayerStatsRequest` |
| `result` | `PlayerChangeResult | UpdateServerPlayerStatsResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_server_start`
**Description:** Triggered after '_start_server'. Start a server, or report that it is already running; failures raise.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_server_start")
async def some_function(self, request, server_name, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `StartServerRequest` |
| `server_name` | `str` |
| `result` | `StartServerResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_server_status_change`
**Description:** Server status configuration change.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, status`

### Listener Signature:
```python
@app_event("after_server_status_change")
async def some_function(self, server_name, status, request, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `server_name` | `str` |
| `status` | `str` |
| `request` | `StatusRequest` |
| `result` | `StatusResult` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_server_stop`
**Description:** Triggered after 'stop_server'. Stop a server, or report that it is already stopped; failures raise.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_server_stop")
async def some_function(self, request, server_name, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `StopServerRequest` |
| `server_name` | `str` |
| `result` | `StopServerResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_server_update`
**Description:** Triggered after 'update_server'. Updates an existing server instance.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_server_update")
async def some_function(self, request, server_name, send_message, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `UpdateServerRequest` |
| `server_name` | `str` |
| `send_message` | `bool` |
| `result` | `UpdateServerResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_set_plugin_status`
**Description:** Triggered after 'set_plugin_status'. Set the enabled/disabled status for a specific plugin.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `plugin_name, enabled`

### Listener Signature:
```python
@app_event("after_set_plugin_status")
async def some_function(self, request, plugin_name, enabled, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetPluginStatusRequest` |
| `plugin_name` | `str` |
| `enabled` | `bool` |
| `result` | `SetPluginStatusResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_set_server_setting`
**Description:** Triggered after 'set_server_setting'. Writes any value to a server's specific persisted configuration
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, key`

### Listener Signature:
```python
@app_event("after_set_server_setting")
async def some_function(self, request, server_name, key, value, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetServerSettingRequest` |
| `server_name` | `str` |
| `key` | `str` |
| `value` | `JsonValue` |
| `result` | `SetServerSettingResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_setting_update`
**Description:** Triggered after 'set_global_setting'. Writes a value to the global application settings.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `key`

### Listener Signature:
```python
@app_event("after_setting_update")
async def some_function(self, request, key, value, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetGlobalSettingRequest` |
| `key` | `str` |
| `value` | `JsonValue` |
| `result` | `SetGlobalSettingResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_world_export`
**Description:** Triggered after 'export_world'. Export the server's currently active world to a .mcworld archive.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, export_dir`

### Listener Signature:
```python
@app_event("after_world_export")
async def some_function(self, request, server_name, export_dir, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ExportWorldRequest` |
| `server_name` | `str` |
| `export_dir` | `str | None` |
| `result` | `ExportWorldResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_world_import`
**Description:** Triggered after 'import_world'. Import a world from a .mcworld file, replacing the active world.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, selected_file_path`

### Listener Signature:
```python
@app_event("after_world_import")
async def some_function(self, request, server_name, selected_file_path, stop_start_server, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ImportWorldRequest` |
| `server_name` | `str` |
| `selected_file_path` | `str` |
| `stop_start_server` | `bool` |
| `result` | `ImportWorldResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `after_world_reset`
**Description:** Triggered after 'reset_world'. Resets the server's world by deleting the active world directory.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("after_world_reset")
async def some_function(self, request, server_name, result, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ResetWorldRequest` |
| `server_name` | `str` |
| `result` | `ResetWorldResponse` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `backup_activity`
**Description:** Backup capture, verification, or destination copy outcome; no credentials or file values.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, backup_id, action`

### Listener Signature:
```python
@app_event("backup_activity")
async def some_function(self, server_name, backup_id, action, status, destination, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `server_name` | `str` |
| `backup_id` | `str` |
| `action` | `Literal['capture', 'verify', 'copy', 'delete']` |
| `status` | `Literal['completed', 'failed']` |
| `destination` | `str | None` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `backup_attention`
**Description:** Deduplicated recovery readiness alert without secret values.
- **Cancellable:** No
- **Identity Keys (for re-entrancy):** `server_name, alert_id`

### Listener Signature:
```python
@app_event("backup_attention")
async def some_function(self, server_name, alert_id, message, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `server_name` | `str` |
| `alert_id` | `str` |
| `message` | `str` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_add_server_ban`
**Description:** Triggered before 'add_server_ban'. Adds a player to the server ban list.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, xuid`

### Listener Signature:
```python
@app_event("before_add_server_ban")
async def some_function(self, request, server_name, player_name, xuid, reason, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `AddServerBanRequest` |
| `server_name` | `str` |
| `player_name` | `str` |
| `xuid` | `str` |
| `reason` | `str | None` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_addon_disable`
**Description:** Triggered before 'disable_addon'. Disables an active addon for a server's active world, preserving files.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, pack_uuid`

### Listener Signature:
```python
@app_event("before_addon_disable")
async def some_function(self, request, server_name, pack_uuid, pack_type, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `DisableAddonRequest` |
| `server_name` | `str` |
| `pack_uuid` | `str` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_addon_enable`
**Description:** Triggered before 'enable_addon'. Enables a disabled addon for a server's active world.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, pack_uuid`

### Listener Signature:
```python
@app_event("before_addon_enable")
async def some_function(self, request, server_name, pack_uuid, pack_type, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `EnableAddonRequest` |
| `server_name` | `str` |
| `pack_uuid` | `str` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_addon_import`
**Description:** Triggered before 'import_addon'. Installs an addon to a specified Bedrock server.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, addon_file_path`

### Listener Signature:
```python
@app_event("before_addon_import")
async def some_function(self, request, server_name, addon_file_path, stop_start_server, restart_only_on_success, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ImportAddonRequest` |
| `server_name` | `str` |
| `addon_file_path` | `str` |
| `stop_start_server` | `bool` |
| `restart_only_on_success` | `bool` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_addon_reorder`
**Description:** Triggered before 'reorder_addons'. Reorder the active addons for a server's active world.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_addon_reorder")
async def some_function(self, request, server_name, uuids, pack_type, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ReorderAddonsRequest` |
| `server_name` | `str` |
| `uuids` | `list[str]` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_addon_subpack_update`
**Description:** Triggered before 'update_subpack'. Updates the active subpack for an addon on a server's active world.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, pack_uuid`

### Listener Signature:
```python
@app_event("before_addon_subpack_update")
async def some_function(self, request, server_name, pack_uuid, pack_type, subpack_name, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `UpdateSubpackRequest` |
| `server_name` | `str` |
| `pack_uuid` | `str` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `subpack_name` | `str` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_addon_uninstall`
**Description:** Triggered before 'uninstall_addon'. Uninstalls an addon for a server's active world, deleting its files.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, pack_uuid`

### Listener Signature:
```python
@app_event("before_addon_uninstall")
async def some_function(self, request, server_name, pack_uuid, pack_type, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `UninstallAddonRequest` |
| `server_name` | `str` |
| `pack_uuid` | `str` |
| `pack_type` | `Literal['behavior', 'resource']` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_allowlist_change`
**Description:** Triggered before 'remove_from_allowlist'. Remove a list of players from the server's allowlist.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_allowlist_change")
async def some_function(self, *, request, server_name, new_players_data=None, player_names=None, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `AddToAllowlistRequest | RemoveFromAllowlistRequest` |
| `server_name` | `str` |
| `new_players_data` | `list[bedrock_server_manager.api.models.allowlist.AllowlistPlayer]` |
| `player_names` | `list[str]` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_backup`
**Description:** Triggered before 'create_server_backup'. Capture one coherent, optionally encrypted server archive.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_backup")
async def some_function(self, *, request, server_name, file_to_backup=None, encrypted=None, include_packs=None, purpose=None, schedule_slot=None, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `BackupWorldRequest | BackupConfigFileRequest | BackupAllRequest | CreateSnapshotRequest` |
| `server_name` | `str` |
| `file_to_backup` | `str` |
| `encrypted` | `bool | None` |
| `include_packs` | `bool | None` |
| `purpose` | `Literal['manual', 'scheduled']` |
| `schedule_slot` | `str | None` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_command_send`
**Description:** Triggered before 'send_command'. Sends a command to a running Bedrock server.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, command`

### Listener Signature:
```python
@app_event("before_command_send")
async def some_function(self, request, server_name, command, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SendCommandRequest` |
| `server_name` | `str` |
| `command` | `str` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_delete_server_data`
**Description:** Triggered before 'delete_server_data'. Delete all data associated with a Bedrock server.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_delete_server_data")
async def some_function(self, request, server_name, stop_if_running, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `DeleteServerDataRequest` |
| `server_name` | `str` |
| `stop_if_running` | `bool` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_permission_change`
**Description:** Triggered before 'set_permissions'. Set a player's permission level for a given server.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, xuid`

### Listener Signature:
```python
@app_event("before_permission_change")
async def some_function(self, request, server_name, xuid, player_name, permission, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetPermissionsRequest` |
| `server_name` | `str` |
| `xuid` | `str` |
| `player_name` | `str | None` |
| `permission` | `Literal['visitor', 'member', 'operator']` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_player_db_scan`
**Description:** Triggered before 'scan_and_update_player_db'. Scans all server logs to discover and save player data.
- **Cancellable:** Yes (`event.cancel()`)

### Listener Signature:
```python
@app_event("before_player_db_scan")
async def some_function(self, request, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ScanAndUpdatePlayerDbRequest` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_players_add`
**Description:** Triggered before 'add_players_manually'. Adds or updates player data in the database.
- **Cancellable:** Yes (`event.cancel()`)

### Listener Signature:
```python
@app_event("before_players_add")
async def some_function(self, request, player_strings, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `AddPlayersManuallyRequest` |
| `player_strings` | `list[str]` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_properties_change`
**Description:** Triggered before 'set_properties'. Set one or multiple server properties for a given server.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_properties_change")
async def some_function(self, request, server_name, properties_to_update, restart_after_modify, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetPropertiesRequest` |
| `server_name` | `str` |
| `properties_to_update` | `dict[str, str]` |
| `restart_after_modify` | `bool` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_prune_backups`
**Description:** Triggered before 'prune_old_backups'. Prunes old backups for a server based on retention settings.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_prune_backups")
async def some_function(self, request, server_name, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `PruneOldBackupsRequest` |
| `server_name` | `str` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_prune_download_cache`
**Description:** Triggered before 'prune_download_cache'. Prunes old downloaded server archives (.zip) in a directory.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `download_dir, keep_count`

### Listener Signature:
```python
@app_event("before_prune_download_cache")
async def some_function(self, request, download_dir, keep_count, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `PruneDownloadCacheRequest` |
| `download_dir` | `str` |
| `keep_count` | `int | None` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_remove_server_ban`
**Description:** Triggered before 'remove_server_ban'. Remove a player from the server ban list.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, xuid`

### Listener Signature:
```python
@app_event("before_remove_server_ban")
async def some_function(self, request, server_name, xuid, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `RemoveServerBanRequest` |
| `server_name` | `str` |
| `xuid` | `str` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_restore`
**Description:** Triggered before 'recover_server_backup'. Retry an interrupted restore's recovery while preserving its journal on failure.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_restore")
async def some_function(self, *, request, server_name, stop_start_server=None, backup_file_path=None, component=None, backup_id=None, components=None, token=None, restart=None, stop_running=None, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `RestoreAllRequest | RestoreWorldRequest | RestoreConfigFileRequest | RestoreSnapshotRequest | ListSnapshotsRequest` |
| `server_name` | `str` |
| `stop_start_server` | `bool` |
| `backup_file_path` | `str` |
| `component` | `Literal['server.properties', 'allowlist.json', 'permissions.json'] | None` |
| `backup_id` | `str` |
| `components` | `list[Literal['server_directory', 'world', 'server.properties', 'allowlist.json', 'permissions.json', 'script_config', 'bsm_settings', 'behavior_packs', 'resource_packs', 'development_behavior_packs', 'development_resource_packs']]` |
| `token` | `str` |
| `restart` | `bool` |
| `stop_running` | `bool` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_server_install`
**Description:** Triggered before 'install_new_server'. Installs a new server instance.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, target_version`

### Listener Signature:
```python
@app_event("before_server_install")
async def some_function(self, request, server_name, target_version, server_zip_path, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `InstallNewServerRequest` |
| `server_name` | `str` |
| `target_version` | `str` |
| `server_zip_path` | `str | None` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_server_players_change`
**Description:** Triggered before 'update_server_player_stats'. Internal API to trigger player stat updates for websockets/plugins.
- **Cancellable:** Yes (`event.cancel()`)

### Listener Signature:
```python
@app_event("before_server_players_change")
async def some_function(self, server_name, player_count, players, request, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `server_name` | `str` |
| `player_count` | `int` |
| `players` | `list[bedrock_server_manager.events.player.PlayerPresence] | list[bedrock_server_manager.api.models.common.PlayerInfo]` |
| `request` | `PlayerSnapshot | UpdateServerPlayerStatsRequest` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_server_start`
**Description:** Triggered before '_start_server'. Start a server, or report that it is already running; failures raise.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_server_start")
async def some_function(self, request, server_name, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `StartServerRequest` |
| `server_name` | `str` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_server_status_change`
**Description:** Server status configuration change.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, status`

### Listener Signature:
```python
@app_event("before_server_status_change")
async def some_function(self, server_name, status, request, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `server_name` | `str` |
| `status` | `str` |
| `request` | `StatusRequest` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_server_stop`
**Description:** Triggered before 'stop_server'. Stop a server, or report that it is already stopped; failures raise.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_server_stop")
async def some_function(self, request, server_name, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `StopServerRequest` |
| `server_name` | `str` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_server_update`
**Description:** Triggered before 'update_server'. Updates an existing server instance.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_server_update")
async def some_function(self, request, server_name, send_message, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `UpdateServerRequest` |
| `server_name` | `str` |
| `send_message` | `bool` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_set_plugin_status`
**Description:** Triggered before 'set_plugin_status'. Set the enabled/disabled status for a specific plugin.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `plugin_name, enabled`

### Listener Signature:
```python
@app_event("before_set_plugin_status")
async def some_function(self, request, plugin_name, enabled, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetPluginStatusRequest` |
| `plugin_name` | `str` |
| `enabled` | `bool` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_set_server_setting`
**Description:** Triggered before 'set_server_setting'. Writes any value to a server's specific persisted configuration
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, key`

### Listener Signature:
```python
@app_event("before_set_server_setting")
async def some_function(self, request, server_name, key, value, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetServerSettingRequest` |
| `server_name` | `str` |
| `key` | `str` |
| `value` | `JsonValue` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_setting_update`
**Description:** Triggered before 'set_global_setting'. Writes a value to the global application settings.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `key`

### Listener Signature:
```python
@app_event("before_setting_update")
async def some_function(self, request, key, value, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `SetGlobalSettingRequest` |
| `key` | `str` |
| `value` | `JsonValue` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_world_export`
**Description:** Triggered before 'export_world'. Export the server's currently active world to a .mcworld archive.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, export_dir`

### Listener Signature:
```python
@app_event("before_world_export")
async def some_function(self, request, server_name, export_dir, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ExportWorldRequest` |
| `server_name` | `str` |
| `export_dir` | `str | None` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_world_import`
**Description:** Triggered before 'import_world'. Import a world from a .mcworld file, replacing the active world.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name, selected_file_path`

### Listener Signature:
```python
@app_event("before_world_import")
async def some_function(self, request, server_name, selected_file_path, stop_start_server, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ImportWorldRequest` |
| `server_name` | `str` |
| `selected_file_path` | `str` |
| `stop_start_server` | `bool` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `before_world_reset`
**Description:** Triggered before 'reset_world'. Resets the server's world by deleting the active world directory.
- **Cancellable:** Yes (`event.cancel()`)
- **Identity Keys (for re-entrancy):** `server_name`

### Listener Signature:
```python
@app_event("before_world_reset")
async def some_function(self, request, server_name, event, **kwargs):
    pass
```
### Available `kwargs`:
| Key Name | Type |
|----------|------|
| `request` | `ResetWorldRequest` |
| `server_name` | `str` |
| `event` | `CancellableEvent` |
| `_triggering_plugin` | `str` (core, or plugin name) |

---


## `on_load`
**Description:** Application lifecycle notification.
- **Cancellable:** No

### Listener Signature:
```python
@app_event("on_load")
async def some_function(self, **kwargs):
    pass
```

---


## `on_manager_startup`
**Description:** Application lifecycle notification.
- **Cancellable:** No

### Listener Signature:
```python
@app_event("on_manager_startup")
async def some_function(self, **kwargs):
    pass
```

---


## `on_unload`
**Description:** Application lifecycle notification.
- **Cancellable:** No

### Listener Signature:
```python
@app_event("on_unload")
async def some_function(self, **kwargs):
    pass
```
