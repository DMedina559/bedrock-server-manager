# Back up and restore a server

BSM creates one portable `.bsmbackup` archive for each backup operation. The same operation is used for manual backups, backup before an update, and the backup-on-start plugin.

## What a backup includes

| Component | Contents |
|---|---|
| World | The active world directory, including embedded packs and activation files |
| Server properties | `server.properties` |
| Allowlist | `allowlist.json`, when present |
| Player permissions | `permissions.json`, when present |
| Script configuration | The server's complete `config/` directory, including variables, secrets, and module permissions |
| BSM server settings | Autostart, autoupdate, target version, and custom settings for this server |

Missing optional components are recorded as absent. An unreadable existing source fails creation. A newly installed server without a generated world can have a configuration-only backup; the manifest shows its actual coverage.

Executables, logs, running-process state, global BSM users and settings, other servers, and backup encryption keys are excluded. Packs and other dependencies outside the active world's directory are not included. Keep such external content separately.

This is a server backup, not a complete BSM installation backup. Preserve the BSM database and host credentials separately when migrating the manager itself.

## Create a backup

Open the server's **Backups** page, choose the encryption policy, and select **Create backup**. The configured default also applies to automatic backups. Check the operation outcome before relying on the new archive.

A running server uses Bedrock's save hold/query/resume mechanism. BSM copies the world while saves are held, resumes saves, then compresses and encrypts the captured data. Changes made outside BSM may not participate in its configuration locks.

Completed backups appear only after verification and atomic publication. Failed creation does not replace existing archives or trigger retention.

## Encryption and emergency kits

An administrator can generate a backup encryption key from **Encryption keys**. Download its emergency kit and store it outside the BSM host. Enable encryption for automatic backups or choose it for an individual manual backup.

Encrypted archives use SecureTar v3, with Argon2id and streaming authenticated encryption. Their private manifest, filenames, configuration, settings, and payload are encrypted. A small public header identifies the format and key ID.

BSM retains its current and previous keys in a private host credential store. Rotation changes the active key for future backups. Old archives still require their original key. If the matching key is lost and no host copy or emergency kit remains, the encrypted backup cannot be recovered.

Downloads preserve the stored encryption. Administrators can explicitly export a decrypted copy; that copy contains readable server secrets. Unencrypted backups also contain readable secrets.

The private credential store protects access to keys at rest but does not protect against an administrator or attacker controlling the running BSM host. In-process Python plugins share BSM's operating-system permissions.

## Inspect and selectively restore

1. Select **Inspect / restore** beside an archive, or import a backup file.
2. If needed, enter the matching recovery key. A key already held by BSM can be used automatically.
3. Inspect the source server, world, versions, date, and available components.
4. Select complete components to restore. Absent components are unavailable.
5. Select **Review restore** and check the destination paths, warnings, and space requirements.
6. Confirm replacement. BSM validates and stages the data, stops the Minecraft server, restores selected files and settings, and optionally restarts an originally running server after success.

BSM stays online. Follow progress in the task interface; reopening the page does not restart the operation. Unselected components and other servers are preserved.

World restoration replaces the complete world directory. Script configuration replaces the complete server `config/` directory, including secrets and module permissions; it does not merge newer files into the restored directory.

When restoring the world and properties together, the restored properties determine the world destination. A world-only restore replaces the destination's current active world. A properties-only restore cannot select a missing world: include the world component if required.

BSM settings restoration preserves the destination server's identity, actual installed version, and runtime status. Restoring a target-version preference does not install or downgrade Bedrock.

A plan becomes invalid when the relevant destination configuration or selected archive changes. Review a new plan instead of retrying with an old token.

## Recovery after failure or interruption

Before replacing data, BSM writes a recovery journal inside the server directory. It retains previous selected files and settings until the restore commits.

If restoration fails, BSM attempts recovery and leaves the Minecraft server stopped when the result is uncertain. If rollback cannot complete, preserve the `.bsm-restore` directory and inspect the reported failure. Do not remove its recovery copies merely to make the server start.

At application startup, BSM recovers unfinished restores before loading plugins or autostarting servers. A server with an outstanding journal cannot start through the normal process API. Committed journals are cleaned without reverting successfully restored data.

A server restart failure is reported separately from a successful data restore.

## Retention

`retention.backups` applies to completed unified archives for each server, regardless of world name:

- `0` disables automatic pruning.
- A positive value retains that many completed archives.

BSM applies retention after successful creation. Retention failures are reported separately from the successful backup. Legacy backups and recovery journals are not automatically included in this policy.

**Migration note:** zero previously permitted deleting all matching backups. It now preserves backups until the setting is changed or files are explicitly removed.

## Older backups

The **Legacy backups** section lists existing `.mcworld` and configuration files. Restore each deliberately. Independently dated legacy files do not form one coherent historical snapshot.

Existing backup creation API names are compatibility aliases for unified archive creation. New clients should use the portable archive operations. Legacy restore-all no longer combines independently dated files; it selects one latest unified archive.

Minecraft `.mcworld` import and export remain available as content operations.

## Offline recovery

Install BSM on a recovery machine. These commands do not require the original database or a running BSM instance:

```console
bedrock-server-manager backup inspect server.bsmbackup
bedrock-server-manager backup extract server.bsmbackup recovered-server
```

For encrypted backups, add `--recovery-key` to prompt privately:

```console
bedrock-server-manager backup extract server.bsmbackup recovered-server --recovery-key
```

The destination must not exist. BSM authenticates and validates the archive before publishing extracted contents. It includes `manifest.json` in the extracted directory.

Keep another backup copy outside the BSM host and periodically test recovery.

The backup page displays outstanding recovery state and provides **Retry recovery**. Stop the Minecraft server before retrying an uncommitted rollback. A recovery failure blocks that server's startup but does not intentionally shut down the manager.

Archive processing is bounded by `backups.max_files`, `backups.max_expanded_bytes`, and `backups.max_archive_bytes`. Adjust these limits through application settings when managing unusually large worlds. Temporary and recovery data also require sufficient local disk space.
