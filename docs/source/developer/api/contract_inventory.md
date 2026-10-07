# Complete API contract inventory

Baseline: `dev` commit `c9eea1c14cc4ef2ff0d01ead801ec691edb7552d`.

All 78 data operations across 17 domains are implemented with validated, serializable request and response models. All 59 registered operations expose contract version 2; the ordinary plugin view contains 55 operations. Existing plugin exposure restrictions are preserved. This inventory also includes unregistered application operations.

| Operation | Request model | Response model | Data fields |
| --- | --- | --- | --- |
| `addon.disable_addon` | `DisableAddonRequest` | `DisableAddonResponse` | server_name, pack_uuid, pack_type |
| `addon.enable_addon` | `EnableAddonRequest` | `EnableAddonResponse` | server_name, pack_uuid, pack_type |
| `addon.import_addon` | `ImportAddonRequest` | `ImportAddonResponse` | server_name, addon_file_path, stop_start_server, restart_only_on_success |
| `addon.list_available_addons` | `ListAvailableAddonsRequest` | `ListAvailableAddonsResponse` | (empty) |
| `addon.list_installed_addons` | `ListInstalledAddonsRequest` | `ListInstalledAddonsResponse` | server_name |
| `addon.reorder_addons` | `ReorderAddonsRequest` | `ReorderAddonsResponse` | server_name, uuids, pack_type |
| `addon.uninstall_addon` | `UninstallAddonRequest` | `UninstallAddonResponse` | server_name, pack_uuid, pack_type |
| `addon.update_subpack` | `UpdateSubpackRequest` | `UpdateSubpackResponse` | server_name, pack_uuid, pack_type, subpack_name |
| `allowlist.add_to_allowlist` | `AddToAllowlistRequest` | `AddToAllowlistResponse` | server_name, new_players_data |
| `allowlist.get_allowlist` | `GetAllowlistRequest` | `GetAllowlistResponse` | server_name |
| `allowlist.remove_from_allowlist` | `RemoveFromAllowlistRequest` | `RemoveFromAllowlistResponse` | server_name, player_names |
| `application.get_all_servers_data` | `GetAllServersDataRequest` | `GetAllServersDataResponse` | (empty) |
| `application.get_system_and_app_info` | `GetSystemAndAppInfoRequest` | `GetSystemAndAppInfoResponse` | (empty) |
| `application.list_available_worlds` | `ListAvailableWorldsRequest` | `ListAvailableWorldsResponse` | (empty) |
| `application.update_server_statuses` | `UpdateServerStatusesRequest` | `UpdateServerStatusesResponse` | (empty) |
| `backup_restore.backup_all` | `BackupAllRequest` | `BackupAllResponse` | server_name |
| `backup_restore.backup_config_file` | `BackupConfigFileRequest` | `BackupConfigFileResponse` | server_name, file_to_backup |
| `backup_restore.backup_world` | `BackupWorldRequest` | `BackupWorldResponse` | server_name |
| `backup_restore.list_backup_files` | `ListBackupFilesRequest` | `ListBackupFilesResponse` | server_name, backup_type |
| `backup_restore.prune_old_backups` | `PruneOldBackupsRequest` | `PruneOldBackupsResponse` | server_name |
| `backup_restore.restore_all` | `RestoreAllRequest` | `RestoreAllResponse` | server_name, stop_start_server |
| `backup_restore.restore_config_file` | `RestoreConfigFileRequest` | `RestoreConfigFileResponse` | server_name, backup_file_path, stop_start_server |
| `backup_restore.restore_world` | `RestoreWorldRequest` | `RestoreWorldResponse` | server_name, backup_file_path, stop_start_server |
| `ban.add_server_ban` | `AddServerBanRequest` | `AddServerBanResponse` | server_name, player_name, xuid, reason |
| `ban.get_server_bans` | `GetServerBansRequest` | `GetServerBansResponse` | server_name |
| `ban.remove_server_ban` | `RemoveServerBanRequest` | `RemoveServerBanResponse` | server_name, xuid |
| `install.install_new_server` | `InstallNewServerRequest` | `InstallNewServerResponse` | server_name, target_version, server_zip_path |
| `install.update_server` | `UpdateServerRequest` | `UpdateServerResponse` | server_name, send_message |
| `misc.prune_download_cache` | `PruneDownloadCacheRequest` | `PruneDownloadCacheResponse` | download_dir, keep_count |
| `permissions.get_permissions` | `GetPermissionsRequest` | `GetPermissionsResponse` | server_name |
| `permissions.set_permissions` | `SetPermissionsRequest` | `SetPermissionsResponse` | server_name, xuid, player_name, permission |
| `player.add_players_manually` | `AddPlayersManuallyRequest` | `AddPlayersManuallyResponse` | player_strings |
| `player.get_all_known_players` | `GetAllKnownPlayersRequest` | `GetAllKnownPlayersResponse` | (empty) |
| `player.scan_and_update_player_db` | `ScanAndUpdatePlayerDbRequest` | `ScanAndUpdatePlayerDbResponse` | (empty) |
| `plugins.get_plugin_statuses` | `GetPluginStatusesRequest` | `GetPluginStatusesResponse` | (empty) |
| `plugins.reload_plugins` | `ReloadPluginsRequest` | `ReloadPluginsResponse` | (empty) |
| `plugins.reload_single_plugin` | `ReloadSinglePluginRequest` | `ReloadSinglePluginResponse` | target_plugin_name |
| `plugins.set_plugin_status` | `SetPluginStatusRequest` | `SetPluginStatusResponse` | target_plugin_name, enabled |
| `plugins.trigger_external_app_event` | `TriggerExternalAppEventRequest` | `TriggerExternalAppEventResponse` | event_name, payload |
| `properties.get_properties` | `GetPropertiesRequest` | `GetPropertiesResponse` | server_name |
| `properties.set_properties` | `SetPropertiesRequest` | `SetPropertiesResponse` | server_name, properties_to_update, restart_after_modify |
| `properties.validate_property_value` | `ValidatePropertyValueRequest` | `ValidatePropertyValueResponse` | property_name, value |
| `server.delete_server_data` | `DeleteServerDataRequest` | `DeleteServerDataResponse` | server_name, stop_if_running |
| `server.get_all_server_settings` | `GetAllServerSettingsRequest` | `GetAllServerSettingsResponse` | server_name |
| `server.get_server_setting` | `GetServerSettingRequest` | `GetServerSettingResponse` | server_name, key |
| `server.get_server_summary` | `GetServerSummaryRequest` | `GetServerSummaryResponse` | server_name |
| `server.restart_server` | `RestartServerRequest` | `RestartServerResponse` | server_name, send_message |
| `server.send_command` | `SendCommandRequest` | `SendCommandResponse` | server_name, command |
| `server.set_server_custom_value` | `SetServerCustomValueRequest` | `SetServerCustomValueResponse` | server_name, key, value |
| `server.set_server_setting` | `SetServerSettingRequest` | `SetServerSettingResponse` | server_name, key, value |
| `server.set_server_status` | `SetServerStatusRequest` | `SetServerStatusResponse` | server_name, status |
| `server.start_server` | `StartServerRequest` | `StartServerResponse` | server_name |
| `server.stop_server` | `StopServerRequest` | `StopServerResponse` | server_name |
| `server.update_server_player_stats` | `UpdateServerPlayerStatsRequest` | `UpdateServerPlayerStatsResponse` | server_name, player_count, players |
| `settings.get_all_global_settings` | `GetAllGlobalSettingsRequest` | `GetAllGlobalSettingsResponse` | (empty) |
| `settings.get_global_setting` | `GetGlobalSettingRequest` | `GetGlobalSettingResponse` | key |
| `settings.reload_global_settings` | `ReloadGlobalSettingsRequest` | `ReloadGlobalSettingsResponse` | (empty) |
| `settings.set_custom_global_setting` | `SetCustomGlobalSettingRequest` | `SetCustomGlobalSettingResponse` | key, value |
| `settings.set_global_setting` | `SetGlobalSettingRequest` | `SetGlobalSettingResponse` | key, value |
| `system.get_bedrock_process_info` | `GetBedrockProcessInfoRequest` | `GetBedrockProcessInfoResponse` | server_name |
| `system.get_server_running_status` | `GetServerRunningStatusRequest` | `GetServerRunningStatusResponse` | server_name |
| `web.create_web_ui_service` | `CreateWebUiServiceRequest` | `CreateWebUiServiceResponse` | autostart, system, username, password |
| `web.disable_web_ui_service` | `DisableWebUiServiceRequest` | `DisableWebUiServiceResponse` | system |
| `web.enable_web_ui_service` | `EnableWebUiServiceRequest` | `EnableWebUiServiceResponse` | system |
| `web.get_web_server_status` | `GetWebServerStatusRequest` | `GetWebServerStatusResponse` | (empty) |
| `web.get_web_ui_service_status` | `GetWebUiServiceStatusRequest` | `GetWebUiServiceStatusResponse` | system |
| `web.remove_web_ui_service` | `RemoveWebUiServiceRequest` | `RemoveWebUiServiceResponse` | system |
| `web.start_web_server` | `StartWebServerRequest` | `StartWebServerResponse` | host, port, debug, mode |
| `web.stop_web_server` | `StopWebServerRequest` | `StopWebServerResponse` | (empty) |
| `websocket.broadcast` | `BroadcastRequest` | `BroadcastResponse` | topic, data |
| `websocket.publish_ws_event` | `PublishWsEventRequest` | `PublishWsEventResponse` | event_name, data |
| `websocket.send_to_client` | `SendToClientRequest` | `SendToClientResponse` | client_id, data |
| `websocket.send_to_user` | `SendToUserRequest` | `SendToUserResponse` | username, data |
| `websocket.unregister_data_provider` | `UnregisterDataProviderRequest` | `UnregisterDataProviderResponse` | topic |
| `world.export_world` | `ExportWorldRequest` | `ExportWorldResponse` | server_name, export_dir |
| `world.get_world_name` | `GetWorldNameRequest` | `GetWorldNameResponse` | server_name |
| `world.import_world` | `ImportWorldRequest` | `ImportWorldResponse` | server_name, selected_file_path, stop_start_server |
| `world.reset_world` | `ResetWorldRequest` | `ResetWorldResponse` | server_name |

## Runtime capabilities

These three integrations live in `plugins/runtime_capabilities.py`, outside the data API. Their live callables and context managers remain native Python values. The plugin bridge injects context and trusted identity and rejects overrides.

| Capability | Native result | Plugin access |
| --- | --- | --- |
| `run_task` | Task identifier | `await self.api.run_task(function, *args, username=...)` |
| `server_lifecycle_manager` | Async context manager | `async with self.api.server_lifecycle_manager(...)` |
| `register_data_provider` | Registration acknowledgement | `await self.api.websocket.register_data_provider(topic, handler)` |

`api.errors.error_response` is a transport utility, not an operation. It converts raised failures to a safe error model.
