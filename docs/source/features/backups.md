# Back up and restore a server

BSM stores a server recovery point in one portable `.bsmbackup` archive. Manual,
scheduled, pre-update, and backup-on-start captures use the same format. Restore
lets you inspect that archive and choose which components to replace.

Start with the server's **Backups** page. Available controls depend on the frontend
version installed with BSM. Configure defaults, schedules, retention,
and destinations in **Settings → Backups**. Check the outcome of each operation;
a successful server start alone does not prove that an optional backup succeeded.

## What is included

| Component | Contents |
|---|---|
| World | The active world, including its embedded packs and activation files |
| Server properties | `server.properties` |
| Allowlist | `allowlist.json`, when present |
| Player permissions | `permissions.json`, when present |
| Script configuration | The server's entire `config/` directory, including variables, secrets, and module permissions |
| BSM server settings | This server's autostart, autoupdate, target version, and custom settings |
| Server packs | `behavior_packs/`, `resource_packs/`, `development_behavior_packs/`, and `development_resource_packs/` |

Choose a content mode:

- **World only:** active world, including its world-local packs and activation files.
- **Selected components:** choose from the table above. Global defaults include the first six components and exclude all server-level pack directories.
- **Full server directory:** every world, executable, log, configuration file and server-level pack in this server's directory. BSM server settings are exported separately. Stop the server first and keep backup storage outside the server directory. BSM's reserved `.bsm-*` staging and recovery entries are excluded.

BSM does not classify bundled or custom server packs. Selecting a server pack directory captures the entire directory. World-local packs are always part of the world component.

Configure `backups.mode` (`world`, `selected`, or `full`) and `backups.components` in global settings. Existing `include_packs` request overrides and `backups.include_server_packs` remain supported; the latter defaults to false. Explicit existing settings are preserved. Schedules can inherit defaults or override mode and components.

Missing sources are recorded as absent; `selected_components` distinguishes omitted components from selected sources that do not exist. Unreadable sources and symbolic links fail capture. Archives keep format version **1** with optional selection, platform and executable-permission metadata; older archives remain readable.

Full-directory restore requires a stopped server, the same operating system and architecture, and the same installed Bedrock version. It replaces all ordinary top-level server entries, including removing entries absent from the archive. Review the plan first. A comprehensive full-directory safety archive is created before replacement; the persistent recovery journal rolls back interrupted changes. Other restores continue to make comprehensive component safety archives. Full-directory archives do not support the separate server-copy workflow; use a component archive for that workflow.

These archives cover one server. Global BSM users, settings, database, backup encryption keys and host dependencies remain separate. Preserve those separately to recover the manager installation.

The **Backup on Start** plugin defaults to world only. Set its `backup_mode` to `selected`, `full`, or `default` to override this, and use `components` for selected mode. Its `encryption` setting accepts `default`, `on`, or `off`. Sequence reuse requires a still-valid archive with the requested coverage: a world-only capture cannot satisfy a later full-directory request. A full-directory capture can satisfy a world request. Cancellation of server startup after backup failure remains controlled by `require_complete_backup`.

## Create and download a backup

1. Open the server's **Backups** page.
2. Choose contents and encryption, then select **Create backup**.
3. Wait for completion and check verification and destination-copy results.
4. Download the archive or confirm that a copy exists outside the BSM host.

For a running server, BSM uses Bedrock's save hold/query/resume mechanism to copy
the world while saves are held. It resumes saves before compression and encryption.
Edits made outside BSM do not necessarily participate in its configuration locks.
Operations changing the same server wait for an active capture; read-only
application work can continue.

Full readback verification is **off by default**. Creation validates captured
configuration, records file checksums, and safely writes the archive, but does not
extract it again. New archives show **Unverified**. Enable
`backups.verify_after_create` to verify immediately, select **Verify** manually,
or configure an independent verification schedule. Restore always authenticates
and validates the archive and selected contents. Failed creation
does not replace existing archives or trigger retention. A failed external copy
is reported separately and does not invalidate a completed local backup.

Downloads preserve the archive's encryption. Where supported in a secure browser
context, the native save-file picker streams directly to the chosen file. Other
browsers use a standard download that may buffer the archive. For very large
archives, use a streaming SDK or CLI download if the browser cannot stream to disk.

Labels and notes help identify recovery points, and the list can be searched and
filtered. Labels, notes, pins, and copy history belong to the manager's catalog;
labels and notes do not travel with the downloaded archive.

## Encryption and recovery keys

An administrator can generate an encryption key and download its emergency kit.
Store the kit separately from the BSM host and keep an off-host archive copy.
Enable the encryption default for automatic captures or select encryption when
creating a manual backup. Encryption is disabled by default.

Encrypted archives use SecureTar v3 with Argon2id and authenticated streaming
encryption. The manifest, filenames, settings, and payload are encrypted; a small
public header identifies the format and key ID. Unencrypted archives and explicit
decrypted exports expose readable server secrets.

BSM stores keys privately at `<config_dir>/credentials/backup-keys.json`. Rotating
the active key affects future captures; older archives still require their
original key. Keep their emergency kits. Losing every copy of the matching key
makes an encrypted archive unrecoverable.

Use **Test recovery key** with an emergency-kit key to check that it opens an
archive. This does not prove the kit is safely stored elsewhere. Host permissions
limit access to stored keys, but an administrator or in-process Python plugin
with BSM's operating-system permissions can access them.

## Schedule backup and verification tasks

Use the administrator **Scheduler** page (also linked from Backups) to add named backup or verification jobs. Each job
selects one server. Verification jobs check unverified archives and archives older
than their configured recheck age; they do not create backups. Jobs are paused
until enabled. Existing backup schedules are retained and remain editable through
the existing settings APIs.

Administrators can configure a per-server daily time, weekdays, IANA timezone
(such as `America/Los_Angeles`), catch-up behavior, and staggering window.
Schedules follow daylight-saving changes: repeated hours run once, and a missing
local time moves forward through the daylight-saving gap.

A new, changed, or re-enabled schedule begins with its next occurrence. After a
restart, catch-up runs one capture for the latest missed occurrence instead of
replaying a backlog. With catch-up disabled, occurrences over two minutes late
are skipped. A stable server-specific offset staggers captures, and automatic
work runs serially for each server, with bounded concurrency across servers.

Schedule checkpoints survive restarts and prevent duplicate captures for a
published occurrence. Failed captures back off and stop after three attempts for
that occurrence. Scheduled backups use the normal hooks, encryption default,
pack policy, verification, and retention. See [bundled plugins](default_plugins.md)
for backup-on-start settings and reuse of a completed pre-update backup within
one operation sequence.

## Inspect and restore selected components

Restoration replaces selected data. Inspect the recovery point and review its
changes before confirming.

1. Choose **Inspect / restore** for an archive, or import a `.bsmbackup` file.
2. Supply its recovery key if BSM does not already hold the matching key.
3. Check the source server, world, capture date, versions, and included components.
4. Select the complete components you want to restore.
5. Select **Review restore** and check changes, warnings, and available space.
6. Optionally run a dry run, then confirm replacement and the restart choice.

Uploads are size-limited before multipart spooling and validated before publication.
Supplied recovery keys are not stored in transfer metadata. Review plans expire
when relevant destination configuration or the archive changes; create a fresh
review instead of reusing an invalid plan.

The comparison lists added, replaced, and removed files, with exact totals and up
to 1,000 individual entries. It redacts script secrets, custom setting values,
and player-access contents. A running world's files may keep changing after review.

| Selection | Replacement behavior |
|---|---|
| World only | Replaces the destination server's current active world |
| World and properties | Uses the restored properties to choose the world destination |
| Properties only | Must not select a missing world; include the world when needed |
| Script configuration | Replaces the entire server `config/` directory, including secrets and module permissions |
| Server packs | Replaces each selected pack directory in full |
| BSM server settings | Restores preferences while preserving destination identity, installed version, and runtime status |

Directories are replaced, not merged. Unselected components and unrelated worlds
remain unchanged. A restored target-version preference does not install or
downgrade Bedrock.

BSM validates and stages the archive, stops a running Minecraft server, and makes
a `pre_restore` safety backup before replacement. If safety capture fails, data
replacement does not begin. After replacement commits, BSM can restart a server
that was originally running. BSM itself stays online; follow the operation's
progress and result. A Minecraft restart failure is distinct from data restoration.

### Capacity checks and dry runs

Review reports required and available space for both server and backup volumes,
combining requirements when they share a filesystem. Estimates include extraction,
safety capture, compression, verification, metadata, and headroom. Space is checked
again before stopping Minecraft; another program can still consume it afterward.

A dry run authenticates the archive and stages selected components in a private
temporary directory on the destination filesystem, flushes them, and checks hashes.
It removes its temporary data and leaves live files and process state untouched.
Insufficient space blocks the exercise and restore. A dry run does not launch
Minecraft or prove that every chunk or pack works in the game engine.

### Restore as a new server

An administrator can prepare a destination using an unused server name,
non-conflicting ports, and a chosen Bedrock version. BSM validates the archive,
installs a stopped server, and publishes a pinned prepared archive with the chosen
ports and autostart disabled. Review and restore that archive through the normal
selective flow. No Minecraft process starts automatically. If preparation fails,
inspect any remaining destination before retrying.

## Interrupted or failed restores

BSM writes a recovery journal in the server's `.bsm-restore` directory and retains
previous selected files and settings until commit. On failure, it attempts rollback.
An uncertain result leaves Minecraft stopped. Preserve the journal and recovery
copies if rollback fails; do not delete them to bypass a startup block.

At BSM startup, unfinished restores are recovered before plugin loading and server
autostart. Outstanding journals block normal server startup. Use **Retry recovery**
on the Backups page; stop Minecraft before retrying an uncommitted rollback.
Committed journals are cleaned without undoing successfully restored data.

Safety archives remain available after a successful restore. They preserve the
world actually replaced, even when restored properties select an inactive world.
If current configuration is damaged, BSM can preserve its raw files in a pinned
safety archive flagged for manual inspection or offline extraction.

The source and safety archive receive a protection window, seven days by default.
Safety archives from failed or interrupted restores remain pinned until explicitly
released. Journal recovery and safety archives provide separate recovery paths;
check the operation result before starting the server or removing either.

## Retention and off-host destinations

### Local archives

`retention.backups` controls the normal per-server recovery-point count, across
world names. **Zero disables automatic local pruning.** A positive count enables
pruning after successful creation. Daily, weekly, and monthly buckets retain
additional newest recovery points for their configured periods.

Pins, safety protection, corrupt archives needing attention, and the last
authenticated usable recovery point are preserved. If no archive can be
authenticated using an available key, pruning stops. An optional storage budget
trims eligible older archives but cannot override these protections; it is not a
hard disk quota. Legacy files and recovery journals are outside this policy.

### External copies

Configure a named destination using an existing absolute directory accessible to
the BSM service account. A mounted NAS, network share, or separate disk can supply
that directory. BSM does not create missing mount points or provide cloud storage
authentication.

After local publication, enabled destinations receive unchanged archive bytes in
a server-specific directory. BSM verifies copies before atomic publication and
never overwrites different existing content. Copies have independent results and
retry controls. Automatic retries back off and stop after three attempts; a manual
retry starts a fresh allowance. Unencrypted local archives remain unencrypted in
external copies. Check that the mount is actually available to the service.

Local pruning does not delete external copies. Set each destination's count,
storage budget, and free-space threshold, then use **Preview external cleanup**.
Review the candidates and explicitly confirm **Delete reviewed copies**. Saving
policy alone does not delete files; changed content, protection, or policy requires
a new preview.

Cleanup retains untracked files, pins, safety-protected copies, and the newest
recorded copy. Its index survives local archive removal. Deliberately pruned copies
are not recreated automatically; a manual copy can recreate them. After interrupted
cleanup, open a new preview to reconcile recorded intent and review remaining work.
Changing a destination directory requires a new copy before readiness recognizes
that location as protected.

## Verification, readiness, and recovery drills

Verification authenticates and checks archive contents, including world metadata,
properties, player-access JSON, and the typed settings export. Changed archives
lose their previous verified status until checked again. Verification uses temporary
space and does not modify the server.

The Backups page reports recent captures, verification, storage use, missing keys,
required older keys, copies, and recovery state. Readiness considers backup age,
key availability, configured destination coverage, storage warnings, and drill
results. Diagnostics includes aggregate backup health. Attention notifications are
deduplicated across maintenance passes and restarts; a cleared condition can notify
again if it recurs.

Periodic maintenance skips busy servers and yields to interactive work between
archive operations. Use **Verify**, **Recovery drill**, or destination retry controls
when investigating an individual archive. A drill stages all included components
and checks copied-file hashes without stopping Minecraft or replacing live files.
Neither verification nor a drill proves Minecraft can load the restored world;
test that separately on a restored server.

| Setting | Default | Meaning |
|---|---|---|
| `backups.readiness_max_age_hours` | 48 | Maximum backup age for readiness |
| `backups.verify_after_create` | false | Full readback immediately after capture |
| `backups.verification_interval_hours` | 0 | Periodic verification interval; `0` disables it |
| `backups.recovery_drill_interval_hours` | 0 | Periodic drill interval; `0` disables it |
| `backups.safety_window_hours` | 168 | Restore source and safety-archive protection window |
| `backups.max_files` | 1,000,000 | Maximum archive file count |
| `backups.max_archive_bytes` | 1 TiB | Maximum stored archive size |
| `backups.max_expanded_bytes` | 1 TiB | Maximum expanded payload size |

Archive limits do not reserve disk space. Allow room for temporary extraction,
verification, safety captures, and recovery data when sizing storage.

## Recover on a fresh installation

The source BSM database is not required to recover a server archive.

1. Install BSM and the appropriate Bedrock version on the recovery host.
2. Create or prepare the destination server, keeping it stopped.
3. Import the archive and supply the matching emergency-kit key if encrypted.
4. Review components, replacement paths, and capacity; run a dry run if appropriate.
5. Restore, inspect the outcome, and test the server before relying on it.

The destination retains its identity and unselected components. If the fresh host
has no encryption key, BSM can encrypt the safety archive using the supplied,
validated recovery key. That key stays in memory and is not added to host
credentials; keep its emergency kit for the safety archive too. Configure a host
key and save its kit before future automatic encrypted captures.

### Extract without a running manager

These local commands do not need a running BSM instance or its database:

```console
bedrock-server-manager backup inspect server.bsmbackup
bedrock-server-manager backup extract server.bsmbackup recovered-server
```

For an encrypted archive, add `--recovery-key` to prompt privately:

```console
bedrock-server-manager backup inspect server.bsmbackup --recovery-key
bedrock-server-manager backup extract server.bsmbackup recovered-server --recovery-key
```

The extraction destination must not exist. BSM validates the archive before
publishing extracted components and `manifest.json`. Extraction does not install
Bedrock or automatically turn the extracted layout into a runnable server.

### Export recovery evidence

Use **Recovery report** to download a JSON report of verification, the latest
drill, component review, capacity checks, and restore outcomes. Reports distinguish
committed data changes from restart or cleanup problems. They omit keys, file
contents and paths, filenames, labels, notes, player identities, and configuration
values. Reports include at most 100 archive entries and indicate omitted entries.
A report is evidence, not an archive or an emergency kit; the recovery journal
remains authoritative for interrupted restores.

## Older backup files

Existing `.mcworld` and configuration files appear under **Legacy backups**. Restore
each deliberately: separately dated files are not one coherent recovery point.
They are not automatically included in unified archive retention.

Legacy backup-creation API names now create unified archives. Legacy restore-all
selects one latest unified archive rather than combining separately dated files.
Minecraft `.mcworld` import and export remain available as
[content operations](content_management.md).


### Scheduler persistence and integration

Schedules and their last-run cursor live in the `schedules` database table;
`schedule_runs` retains the latest 100 attempts per schedule. The API returns the
latest 20 attempts, next occurrence, retry status and handler availability. Existing
`backups.schedules` settings are imported idempotently with stable IDs; updates
through the legacy settings API remain supported. Legacy catalog cursors are
preserved on import to avoid repeating an already published capture.

Administrator endpoints are `GET /api/scheduler/schedules`,
`PUT /api/scheduler/schedules/{schedule_id}`, and
`DELETE /api/scheduler/schedules/{schedule_id}`. A running schedule must finish
before removal. Missed occurrences coalesce according to catch-up policy; failed
attempts back off up to three times per occurrence. Shutdown interrupts active
work, and startup records interrupted attempts rather than claiming success.

Plugins can register an async handler with
`self.api.runtime.register_scheduled_task("my_plugin:task", handler)`. The handler
receives keyword arguments `server_name` and `options`. Administrators create the
schedule separately. Task names must use the plugin namespace. Unloaded handlers
become unavailable; schedules remain visible and resume only when their handler
is registered again. Plugin work participates in normal unload cancellation.
Core currently provides only `backup` and `verify` tasks.

The frontend continues using the existing synchronous lifecycle endpoints and
allows start/stop/restart requests to wait beyond its ordinary request timeout.
Server and reverse-proxy timeouts still apply. Event hook limits can be configured
with `events.hook_timeout_seconds` (120 seconds by default, maximum 3600); changes
take effect when BSM restarts. SDK users can choose a suitable `request_timeout`.
Avoid retrying a lifecycle write simply because a connection was interrupted;
check the server and diagnostics first.

Capture-stage durations are available in archive metadata as
`stage_durations_ms` and in the inspection dialog. Verification status remains
separate from successful creation. Retention can use an unchanged, locally
validated capture without performing full extraction; imported archives must be
verified before being used as the retained recovery point. Pinned and protected
archives cannot be deleted with the individual **Delete** action; external copies
remain independent.

### Choosing a timezone

Select **Pacific Time (America/Los_Angeles)** for Pacific time. Do not enter
`PDT` or `PST`: they describe seasonal abbreviations, not a region's recurring
clock rules. The editor defaults to your browser's regional timezone when the
host supports it. A daily 14:42 Pacific schedule stays at 14:42 Pacific through
winter and summer; BSM calculates each occurrence in UTC automatically. Changing
the host timezone does not shift a saved schedule.

The scheduler advertises supported IANA regions and shows a timezone-data warning
when regional data is unavailable. UTC remains usable without timezone files.
BSM depends on the portable `tzdata` package and can read its packaged rules when
the operating system lookup fails. If the dependency is missing from an existing
Python environment, repair it with `python -m pip install --upgrade tzdata` using
the interpreter that runs BSM, then restart BSM.

### Runtime, state and health

Scheduler definitions and cursors commit through the normal Storage transaction
boundary and participate in its contention and failure telemetry. AppState exposes
only committed scheduler records; a failed write does not publish speculative
state. Reloading state also reloads schedules. Run history remains bounded in the
scheduler tables rather than being copied into the application state cache.

Lifecycle startup owns the scheduler loop, and shutdown cancels and drains its
server jobs. Runtime observations include the last tick and active job count.
Application health checks expose the scheduler heartbeat and regional timezone
availability. The scheduler diagnostic section reads committed state without
migrating settings or querying archive history, and distinguishes scheduler issues
from plugin health issues. Runs also produce correlated diagnostic history records.
Existing 4.0 diagnostic metadata shapes remain readable by older consumers.


### Application timezone and timestamps

Set `general.timezone` in Settings → General to an IANA timezone such as
`America/Los_Angeles`. It defaults to `UTC` and supplies the default for new
schedules. Existing schedules retain their explicit timezone; edit each schedule
if you want to move it. API callers omitting the timezone on an existing schedule
retain that schedule's timezone.

Backup manifests, event and diagnostic timestamps, logs, and timestamped filenames
use UTC. Changing the application timezone changes display defaults, never the
recorded instant or archive identity. The frontend account display preference can
use the application timezone, the browser timezone, or UTC. Timestamp details show
the exact UTC instant. Raw log text remains in UTC.

`GET /api/info` includes the application timezone in `info.timezone`. Existing
settings APIs and plugin global-setting access support `general.timezone`; no new
endpoint or database migration is needed.
