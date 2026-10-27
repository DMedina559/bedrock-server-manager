# Bundled plugins

BSM ships plugins for common automation and content tools. Check the plugin management view for enabled state and settings; optional policies should match your installation's needs.

| Plugin | Behavior |
|---|---|
| Autostart | Starts servers configured for autostart during application startup |
| Backup on start | Defaults to world-only protection before starting; contents and encryption are configurable, and its failure policy can cancel startup |
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
