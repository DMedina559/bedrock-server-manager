# Availiable Hooks

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

This document provides a complete reference for all default event hooks available to plugins to listen to.

These are all the methods from `PluginBase` that you can override in your plugin class.

## Plugin Lifecycle Events
*   `on_load(self)`
*   `on_unload(self)`
*   `on_manager_startup(self)`

## Server Start/Stop Events
*   `before_server_start(self, server_name: str, mode: str)`
*   `after_server_start(self, server_name: str, result: dict)`
*   `before_server_stop(self, server_name: str)`
*   `after_server_stop(self, server_name: str, result: dict)`

## Server Command Events
*   `before_command_send(self, server_name: str, command: str)`
*   `after_command_send(self, server_name: str, command: str, result: dict)`

## Backup & Restore Events
*   `before_backup(self, server_name: str, backup_type: str, **kwargs)`
*   `after_backup(self, server_name: str, backup_type: str, result: dict, **kwargs)`
*   `before_restore(self, server_name: str, restore_type: str, **kwargs)`
*   `after_restore(self, server_name: str, restore_type: str, result: dict, **kwargs)`
*   `before_prune_backups(self, server_name: str)`
*   `after_prune_backups(self, server_name: str, result: dict)`

## World Management Events
*   `before_world_export(self, server_name: str, export_dir: str)`
*   `after_world_export(self, server_name: str, result: dict)`
*   `before_world_import(self, server_name: str, file_path: str)`
*   `after_world_import(self, server_name: str, result: dict)`
*   `before_world_reset(self, server_name: str)`
*   `after_world_reset(self, server_name: str, result: dict)`

## Addon Management Events
*   `before_addon_import(self, server_name: str, addon_file_path: str)`
*   `after_addon_import(self, server_name: str, result: dict)`

## Server Configuration Events
*   `before_allowlist_change(self, server_name: str, players_to_add: list, players_to_remove: list)`
*   `after_allowlist_change(self, server_name: str, result: dict)`
*   `before_permission_change(self, server_name: str, xuid: str, permission: str)`
*   `after_permission_change(self, server_name: str, xuid: str, result: dict)`
*   `before_properties_change(self, server_name: str, properties: dict)`
*   `after_properties_change(self, server_name: str, result: dict)`

## Server Installation & Update Events
*   `before_server_install(self, server_name: str, target_version: str)`
*   `after_server_install(self, server_name: str, result: dict)`
*   `before_server_update(self, server_name: str, target_version: str)`
*   `after_server_update(self, server_name: str, result: dict)`

## Player Database Events
*   `before_players_add(self, players_data: list)`
*   `after_players_add(self, result: dict)`
*   `before_player_db_scan(self)`
*   `after_player_db_scan(self, result: dict)`

## System & Application Events
*   `before_service_change(self, server_name: str, action: str)`
*   `after_service_change(self, server_name: str, action: str, result: dict)`
*   `before_autoupdate_change(self, server_name: str, new_value: bool)`
*   `after_autoupdate_change(self, server_name: str, result: dict)`
*   `before_prune_download_cache(self, download_dir: str, keep_count: int)`
*   `after_prune_download_cache(self, result: dict)`

## Web Server Events
*   `before_web_server_start(self, mode: str)`
*   `after_web_server_start(self, result: dict)`
*   `before_web_server_stop(self)`
*   `after_web_server_stop(self, result: dict)`