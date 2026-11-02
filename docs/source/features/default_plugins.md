# Bundled plugins

BSM ships built-in plugins for common server lifecycle and maintenance automation. Check the plugin management view for enabled state and settings; optional policies should match your installation's needs.

| Plugin | Behavior |
|---|---|
| Autostart (`autostart_plugin`) | Starts servers configured for autostart during application startup |
| Backup on start (`backup_on_start`) | Defaults to world-only protection before starting; contents and encryption are configurable, and its failure policy can cancel startup |
| Update before start (`update_before_start`) | Checks updates for servers configured for autoupdate |
| Server lifecycle notifications (`server_lifecycle_notifications`) | Warns connected players before server maintenance; configured delays affect operation duration |
| World operation notifications (`world_operation_notifications`) | Announces supported world operations |
| Auto reload configuration (`auto_reload_config`) | Sends supported Bedrock reload commands after access-file changes |

Content upload and download are built-in core endpoints (`/api/content/...`), not plugins.

## Review automation before maintenance

Backup-on-start and update-before-start run as hooks. Inspect their settings and logs to understand what happens before a start operation. A successful start does not by itself prove every optional backup succeeded.

Notification delays are part of the operation's timeline, not the game process's termination policy. Configure lifecycle and service deadlines to allow intentional delays and cleanup.

See [plugin management](../plugins/introduction.md) for installation/reload and [plugin development](../developer/plugins/introduction.md) for hook contracts.

## Backup reuse within an operation

Update-before-start runs before backup-on-start. If an update creates a complete
backup, backup-on-start can reuse it within that same operation sequence rather
than create another copy. Only finished backups for the same server covering the
plugin's requested contents qualify. World-only captures cannot satisfy a
full-directory request; full-directory captures can cover a world-only request.
Failed, partial, skipped, active, incomplete-scope, or unrelated backups do not
suppress required work.

The backup-on-start setting `reuse_sequence_backup` defaults to `true`. A reused
pre-update backup preserves the installation before updating. Set it to `false`
if you also want a separate snapshot after updating and before launch. Independent
later starts require their own backup. `require_complete_backup` continues to
control cancellation when a required pre-start backup cannot complete.

Starting an already-running server skips pre-start automation. An update's own
restart does not trigger another automatic update check. Logs explain when a
qualifying backup is reused.

See [the backup and restore guide](backups.md#back-up-before-starting-minecraft)
for content modes, encryption overrides and pre-start timing.

## Bundled plugin settings reference

Configure these plugins under **Plugins → Plugin Settings** in the Web UI.

### `server_lifecycle_notifications`

Broadcasts in-game `say` warnings before stopping, restarting, updating, or deleting a running server, and announces when a server starts or finishes updating.

| Setting | Default | Range | Description |
|---|---|---|---|
| `enable_notifications` | `true` | `bool` | Master switch for all lifecycle in-game announcements |
| `notify_on_start` | `true` | `bool` | Send an in-game message after a server starts |
| `notify_before_stop` | `true` | `bool` | Warn players and wait `stop_countdown_seconds` before stopping |
| `stop_countdown_seconds` | `10` | `0`–`300` | Delay in seconds after the stop warning before stopping |
| `notify_before_restart` | `true` | `bool` | Warn players and wait `restart_countdown_seconds` before restarting |
| `restart_countdown_seconds` | `10` | `0`–`300` | Delay in seconds after the restart warning before restarting |
| `notify_on_update` | `true` | `bool` | Announce before and after server updates |
| `update_countdown_seconds` | `10` | `0`–`300` | Delay in seconds before stopping a running server for an update |
| `notify_before_delete` | `true` | `bool` | Warn players before a running server is stopped for deletion |
| `delete_countdown_seconds` | `10` | `0`–`300` | Delay in seconds before stopping a server for deletion |

### `world_operation_notifications`

Broadcasts in-game announcements and countdowns around world exports, imports, and resets.

| Setting | Default | Range | Description |
|---|---|---|---|
| `enable_world_notifications` | `true` | `bool` | Master switch for world-operation announcements |
| `notify_on_export` | `true` | `bool` | Announce when a world export starts and finishes |
| `notify_on_import` | `true` | `bool` | Warn players before importing a world and announce completion |
| `import_countdown_seconds` | `10` | `0`–`300` | Countdown in seconds before stopping the server for a world import |
| `notify_on_reset` | `true` | `bool` | Warn players before resetting a world and announce completion |
| `reset_countdown_seconds` | `15` | `0`–`300` | Countdown in seconds before stopping the server for a world reset |

### `auto_reload_config`

Automatically sends Bedrock console reload commands to running servers after configuration or addon changes.

| Setting | Default | Description |
|---|---|---|
| `reload_on_allowlist_change` | `true` | Send `allowlist reload` after allowlist edits |
| `reload_on_permissions_change` | `true` | Send `permission reload` after `permissions.json` edits |
| `reload_on_addon_change` | `false` | Send `reload` after addon changes |

### `autostart_plugin` and `update_before_start`

`autostart_plugin` and `update_before_start` do not use plugin-wide settings tables; instead, they read each server's per-server **Autostart** (`server_info.autostart`) and **Autoupdate** (`server_info.autoupdate`) toggles configured on the server's settings page.
