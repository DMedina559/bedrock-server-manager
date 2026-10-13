# Back up and restore

Create backups before importing content, resetting a world, updating a server or restoring older data. Keep another copy outside the BSM host; backups on the same disk cannot protect against disk loss.

## Choose the backup scope

| Scope | Contents |
|---|---|
| World | The active server world |
| Configuration | Selected properties, allowlist or permissions file |
| All | World and supported configuration categories |

A server backup is not a complete BSM installation backup. Preserve the application's configuration, database, plugin files and other required content separately when migrating the host.

Use your server's backup page to create a backup and confirm it appears in the appropriate category. The configured backup root contains per-server backups; it need not be inside the server directory.

## Restore carefully

Restore replaces the selected current data. Create a fresh backup first, select the intended category and timestamp, and allow BSM's maintenance operation to finish before restarting or changing that server.

Restore-all selects backups across categories. The most recent world and configuration backups can have different timestamps; it does not guarantee a single historical snapshot. Verify the resulting world, properties and player permissions after restoration.

## Automate and retain

Review the installed backup-on-start plugin and its settings before relying on automatic backups. Check that the plugin is enabled and inspect failed operations in the logs. Choose retention limits that match available disk space, and periodically test restoration using a separate server.
