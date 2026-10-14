# Bundled plugins

BSM ships plugins for common automation and content tools. Check the plugin management view for enabled state and settings; optional policies should match your installation's needs.

| Plugin | Behavior |
|---|---|
| Autostart | Starts servers configured for autostart during application startup |
| Backup on start | Backs up supported server data before starting; its complete-backup policy can cancel startup on failure |
| Update before start | Checks updates for servers configured for autoupdate |
| Server lifecycle notifications | Warns connected players before server maintenance; configured delays affect operation duration |
| World operation notifications | Announces supported world operations |
| Auto reload configuration | Sends supported Bedrock reload commands after access-file changes |
| Content uploader | Adds upload tools for supported content archives |
| Download page | Adds downloads for supported content and backup files |

## Review automation before maintenance

Backup-on-start and update-before-start run as hooks. Inspect their settings and logs to understand what happens before a start operation. A successful start does not by itself prove every optional backup succeeded.

Notification delays are part of the operation's timeline, not the game process's termination policy. Configure lifecycle and service deadlines to allow intentional delays and cleanup.

Content tools add plugin-owned routes and interface components. Their availability follows plugin state. Use the [manual content library](../extras/install_content.md) if upload tools are unavailable.

See [plugin management](../plugins/introduction.md) for installation/reload and [plugin development](../developer/plugins/introduction.md) for hook contracts.
