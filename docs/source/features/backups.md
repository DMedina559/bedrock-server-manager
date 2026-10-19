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

## Verification and backup health

Every completed capture and imported archive is authenticated and checked before
publication. Verification also checks world metadata, properties, player access
JSON, and the typed server settings export. It does not launch Minecraft or prove
that Bedrock can load every chunk. Use a separate restored server for that check.

The Backups page shows the last successful capture, verification result, storage
usage, missing recovery keys, older keys still needed by existing archives, and
incomplete destination copies. Diagnostics includes an aggregate backup health
section. A failed destination copy does not invalidate a completed local backup.
A changed archive loses its previous verified status until checked again.

By default, lifecycle-owned maintenance checks for overdue verification every
hour. `backups.verification_interval_hours` defaults to 168; zero disables
periodic verification. Maintenance skips servers with active operations and
retries incomplete copies. Checks can also be run manually with **Verify** or
`bsm-cli backup manage verify`. Verification uses temporary disk space for the
expanded archive and does not modify the server.

## Restore review and safety backups

The restore review shows added, replaced, and removed files, with exact totals
and up to 1,000 individual entries. Properties show readable changes for known
public settings. Other properties and custom BSM setting values are redacted;
script secrets and player access file contents are never shown in the comparison.
World comparisons describe the files observed at review time; running worlds can
continue changing until the server stops.

Before replacement, BSM stops a running server and captures a complete
`pre_restore` safety backup. If that capture fails, replacement does not begin.
Safety backups remain after successful restoration, allowing another reviewed
restore to undo it. Both the source and safety archive are protected from pruning
for `backups.safety_window_hours` (168 hours by default). A safety backup from a
failed or interrupted restore stays pinned until explicitly released; successful
restoration releases that pin and starts its protection window. The recovery journal
continues to protect partially replaced files independently of these archives.
A failed operation can leave Minecraft stopped; inspect its result before starting.

## Retention and pins

Pin an archive to exclude it from local pruning. Daily, weekly, and monthly
settings retain the newest archive in each of the configured number of calendar
buckets, in addition to the normal `retention.backups` count. A count of zero
continues to disable local pruning entirely.

An optional `backups.storage_budget_bytes` trims older eligible recovery points
when the configured policy exceeds the budget. Pins, safety windows, corrupt
archives needing attention, and the last authenticated usable recovery point
are preserved even if this exceeds the budget. BSM never claims a hard disk
quota. If no archive can be authenticated with an available key, pruning stops.

## Off-machine copies

Administrators can configure named directory destinations in **Backup policy and
destinations**, using an existing absolute directory on the BSM host. A mounted
NAS, network share, or separately mounted disk can supply that directory. Keep
mounts available to the BSM service account. The mount directory must already
exist; BSM does not create a missing mount point.

After a local archive is complete, each enabled destination receives its unchanged
bytes under a server-specific directory. Copies use a private temporary file,
checksum verification, and atomic publication. Existing different content is
never replaced. Each destination has its own success/failure state and retry
command. Local pruning does not remove remote copies. These destinations do not
provide S3 or cloud authentication; additional adapters can implement the same
publication interface later. An unencrypted archive remains unencrypted remotely.

## Restore as a new server

An administrator can prepare a new server from an archive by choosing an unused
name, non-conflicting ports, and a Bedrock version. BSM validates the archive first,
installs a stopped destination, and publishes a pinned prepared archive with the
chosen ports and autostart disabled. Select that server and review the prepared
archive through the ordinary selective restore flow. No Minecraft process starts
automatically. If installation or preparation fails, inspect the destination
before retrying; completed installation work is not silently deleted.

## Native upload and download

The browser uploads archive files directly through authenticated multipart HTTP,
with progress and cancellation. Uploads are bounded before multipart spooling;
archives are validated before becoming available. Recovery keys are supplied
separately and never saved with transfer metadata.

Downloads preserve the stored archive and encryption. On browsers supporting a
native save-file picker in a secure context, BSM streams bytes directly into the
chosen file with progress and backpressure. Other browsers use the standard
browser download fallback, which may buffer the archive. Use the CLI streaming
download for very large archives on those browsers. Cancelling a native save
aborts its temporary file. The Python SDK and CLI stream downloads to disk.

Use **Test recovery key** with the key from an emergency kit to authenticate an
encrypted archive before an emergency. A successful test proves that key can
open that archive; it cannot prove that an emergency kit has been stored safely
off the host. Rotation retains older keys because existing archives still need them.

Safety archives preserve the world that will actually be replaced, including an
inactive destination world selected by restored properties. Restoring that safety
archive puts the world back at its original destination. Unrelated worlds remain
on disk. If current configuration is damaged, BSM can still preserve its raw files
before a repair restore; that safety archive remains pinned and is flagged for
manual inspection or offline extraction.
