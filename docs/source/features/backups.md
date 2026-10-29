# Back up and restore a server

BSM stores a server recovery point in one portable `.bsmbackup` archive. Manual,
scheduled, pre-update, and backup-on-start captures use the same format. Restore
lets you inspect that archive and choose which components to replace.

Start with the server's **Backups** page. Available controls depend on the frontend
version installed with BSM. Configure defaults, retention and destinations in
**Global Settings → Backups**, and automatic jobs on the **Scheduler** page.
Check each operation's outcome: a successful server start alone does not prove
that an optional backup succeeded.

```{figure} ../../images/web_server_backup_restore.png
:alt: Earlier BSM backup page showing separate world and configuration backups.
:width: 100%

Earlier backup-page layout. This screenshot is awaiting an update; use the
unified archive workflow described below.
```

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

The same component choices are available in manual creation, global defaults,
schedules and Backup on Start settings. Select at least one component in
**Selected components** mode. Full-directory contents are selected through
**Full server directory** mode, rather than an individual component checkbox.

BSM does not classify bundled or custom server packs. Selecting a server pack
directory captures the entire directory. World-local packs are always part of the
world component.

In **Global Settings → Backups**, choose the default mode and components. Manual
backups and schedules can use those defaults or override them. New defaults
exclude server-level packs. Saved `include_server_packs` settings are converted
to component selections when loaded; that flag and the `include_packs` request
override are no longer accepted. Select the desired pack directories explicitly.

| Setting | Default | Purpose |
|---|---|---|
| `backups.mode` | `selected` | World only, selected components, or full directory |
| `backups.components` | World, properties, allowlist, permissions, script configuration and BSM server settings | Contents used in selected mode |
| `backups.encryption` | `false` | Encryption default, overridable for an individual capture |
| `backups.verify_after_create` | `false` | Optional full readback after creation |

A full-directory default also requires servers to be stopped for captures. For
frequent pre-start protection, world only avoids copying binaries and bundled
server packs.

Missing sources are recorded as absent; the manifest's `selected_components` list
distinguishes omitted components from selected sources that do not exist.
Unreadable sources and symbolic links fail capture. Archives keep format version
**1** with optional selection, platform and executable-permission metadata; older
archives remain readable.

These archives cover one server. Global BSM users, settings, database, backup
encryption keys and host dependencies remain separate. Preserve those separately
to recover the manager installation.

## Create and download a backup

1. Open the server's **Backups** page.
2. Choose a content mode and encryption. In selected mode, check the components
   to include. Stop Minecraft first for a full-directory capture.
3. Select **Create backup**.
4. Wait for completion and check verification and destination-copy results.
5. Download the archive or confirm that a copy exists outside the BSM host.

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

Use **Inspect** to open the archive dialog. **Restore options** covers inspection
and restore review, **Details** shows inventory and capture timings, and **Manage**
contains archive-management controls. The row's three-dot menu contains additional
actions such as **Recovery drill**, pinning and deletion.

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

Open **Scheduler** as an administrator and select **Add schedule**. Give the job
an ID using letters, digits, underscores, dots or hyphens (1–100 characters, no
spaces), choose a server, and select **Backup** or **Verify backups**. New jobs are
paused until enabled.

- **Backup** jobs use the global encryption default. Their content picker can
  inherit global contents or choose any of the same three modes as manual
  creation. A full-directory job requires Minecraft to be stopped when it runs.
- **Verify backups** jobs check unverified archives and archives older than the
  configured recheck age. They do not create backups or run Minecraft.

Choose a daily time, weekdays, timezone, catch-up behavior and staggering window.
BSM stores schedules and run history across restarts. The page shows the next run,
recent outcomes and whether the task is available. Existing backup schedules are
retained. A running job must finish before its schedule can be removed.

### Timezones and timestamps

Set the application timezone in **Global Settings → General** using an IANA region
such as `America/Los_Angeles`. The setting is `general.timezone`, which defaults
to `UTC`. New schedules use the application timezone when available; existing jobs
keep their saved timezone until edited.

For Pacific time, choose `America/Los_Angeles`, rather than `PDT` or `PST`. A daily
14:42 job remains at 14:42 Pacific through winter and summer. BSM calculates UTC
occurrences from the saved region. Repeated daylight-saving hours run once; a
missing local time moves forward through the daylight-saving gap. Changing the
host timezone does not shift a saved job.

BSM includes the portable `tzdata` dependency. If the scheduler reports missing
regional timezone data, UTC remains available. Repair `tzdata` in the Python
environment running BSM and restart the manager before using regional schedules.

Backup manifests, event and diagnostic timestamps, log timestamps and timestamped
filenames use UTC. The frontend account display preference can show application
time, browser-local time or UTC; timestamp details show the exact UTC instant.
Changing display timezone does not rename archives or change their recorded time.
Raw log text remains in UTC.

### Missed runs and failures

A new, changed or re-enabled job begins with its next occurrence. With catch-up
enabled, a restart runs the latest missed occurrence rather than replaying every
missed run. Without catch-up, occurrences more than two minutes late are skipped.
A stable server-specific offset provides staggering. Work runs serially per
server, with bounded concurrency across servers.

Persisted checkpoints prevent duplicate captures for a published occurrence.
Failures back off and stop after three attempts for that occurrence. Interrupted
runs are recorded on startup. Unavailable plugin-provided tasks remain visible
and require their plugin to register the handler again before they can resume.
BSM provides backup and verification tasks; plugins may add other task types.

Scheduled backups use the normal hooks, encryption defaults, optional verification,
retention and destination-copy policies. Scheduler status is also included in
application health and diagnostics, including its heartbeat, active jobs and
recorded run failures.

## Back up before starting Minecraft

Configure **Backup on Start** under **Plugin Settings**. It defaults to **world
only**, independently of global backup contents, and includes that world's local
packs. Leave its server selection empty to cover all valid servers.

| Plugin setting | Default | Behavior |
|---|---|---|
| `enable_backup_on_start` | `true` | Back up before starting selected servers |
| `backup_mode` | `world` | Choose `world`, `selected`, `full`, or `default` to use global contents |
| `components` | The six standard data/settings components | Used only in selected mode |
| `encryption` | `default` | Inherit global encryption, or force `on` or `off` |
| `reuse_sequence_backup` | `true` | Reuse an eligible backup from the same operation sequence |
| `require_complete_backup` | `false` | Cancel startup if the requested backup cannot complete |

Update Before Start runs first. Backup on Start can reuse a valid, completed
pre-update capture for the same server if it covers the currently requested
contents. A world-only backup cannot satisfy a full-directory request; a
full-directory capture can satisfy a world-only request. An unrelated or deleted
archive does not suppress the pre-start capture. Set reuse to false for a separate
capture after updating. Independent later starts require their own backup.

A long backup can delay the start operation. The frontend allows existing
start/stop/restart requests to wait beyond its normal request timeout; server and
reverse-proxy timeouts still apply. Event hooks have a separate configured timeout
(`events.hook_timeout_seconds`, 120 seconds by default, up to 3600; restart BSM
after changes). Allow enough time for the selected contents. If a connection drops,
check server status and diagnostics before retrying the write. A successful start
does not prove that an optional pre-start backup completed.

## Inspect and restore selected components

Restoration replaces selected data. Inspect the recovery point and review its
changes before confirming.

1. Choose **Inspect** beside an archive, or import a `.bsmbackup` file first.
2. In **Restore options**, supply a recovery key if needed and select **Inspect**
   to read the archive. Stop Minecraft first to review a full-directory restore.
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
| Full server directory | Replaces all ordinary server-directory entries and removes entries absent from the archive |

Directories are replaced, not merged. With individual component restores,
unselected components and unrelated worlds remain unchanged. Full-directory
restore covers every world and ordinary file in the server directory. A restored
target-version preference does not install or downgrade Bedrock.

BSM validates and stages the archive, stops a running Minecraft server, and makes
a `pre_restore` safety backup before replacement. If safety capture fails, data
replacement does not begin. After replacement commits, BSM can restart a server
that was originally running. BSM itself stays online; follow the operation's
progress and result. A Minecraft restart failure is distinct from data restoration.

### Full-directory restore

Full-directory restore requires the same operating system, architecture and
installed Bedrock version as the capture. It cannot be combined with individual
file components in the same restore selection; BSM server settings can be selected
alongside it. Stop Minecraft before review, dry run or a recovery drill for this
mode. A stopped server stays stopped after restore; start it separately when ready.

Before replacing full-directory contents, BSM makes a full-directory safety archive
of the current server, including files that the restore would remove. Individual
component restores instead make a comprehensive component safety archive. Both
use the persistent recovery journal for rollback and require backup storage outside
the content being captured. BSM's reserved `.bsm-*` staging and journal directories
are not copied or replaced as server data.

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

Use a selected-component archive containing server properties for this workflow;
full-directory archives cannot prepare a separate server copy.

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

Pins, safety protection, corrupt archives needing attention, and the last usable
recovery point are preserved. An unchanged, locally validated capture can serve
as that recovery point while still showing **Unverified**; retention does not
automatically extract it for verification. Imported archives must be verified
before they can supply that protection. If no trusted recovery point is available,
pruning stops. An optional storage budget
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

**Verified** means the archive passed a readback check. **Unverified** is normal
for a newly created archive when immediate verification is disabled; it does not
mean creation failed. Changed archive bytes invalidate a previous verified status.

| Action | What it checks | Live-server effects |
|---|---|---|
| **Verify** | Opens/decrypts the archive, checks inventory, file sizes and hashes, and validates supported world/configuration metadata | No live files changed and Minecraft is not stopped |
| **Dry run** | Reviews a chosen restore selection, checks capacity, extracts into private staging on the destination filesystem, flushes it and reads it back to check hashes | No replacement or Minecraft startup; full-directory review requires Minecraft already stopped |
| **Recovery drill** | Runs the dry-run restore checks for every included component and records a passed/failed result for readiness | No replacement or Minecraft startup; full-directory archives require Minecraft already stopped and compatible platform/version |

All three can read substantial data and require temporary disk space. Verification
after creation and periodic verification/drills are disabled by default. Run checks
manually or configure an appropriate interval. Verification schedules are separate
from backup schedules. Neither a verified archive nor a passed drill proves
Minecraft can load the restored world: test that on a separate restored server.

The Backups page reports recent captures, verification, missing keys, copies,
storage use and pending recovery. **Details** also shows capture-stage timings so
world copying, compression, encryption and optional verification can be compared.
Readiness considers backup age, key availability, destination coverage, storage
warnings and drill results. Application diagnostics includes aggregate backup
health and scheduler observations. Attention notifications are deduplicated across
maintenance passes and restarts; a cleared condition can notify again if it recurs.

Periodic maintenance skips busy servers and yields between archive operations.
Pins and active safety-protection windows also block the individual **Delete**
action. External copies retain their independent policy and cleanup flow.

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

### Scheduler execution and controls

Schedules activate when saved, so the first poll shortly after their due time can
still execute them. Catch-up controls missed first attempts; it does not disable
retries of a run that already started. Automatic failures receive up to three
attempts with backoff, within a one-day retry window. Interactive contention defers
work without consuming that budget. A new occurrence has a separate budget.

The scheduler page provides **Run now**, **Pause/Resume**, and **Retry now**. Manual
runs use distinct execution identities and do not consume a calendar occurrence.
Pausing prevents future claims; an already claimed run may finish. Retry now is an
explicit request to retry a failed slot. Controls can include the listed
configuration revision to reject stale requests. Run history remains the source
of outcomes; acknowledgement of a control does not mean its work has completed.

Listings distinguish `next_run_at` (the next calendar occurrence) from
`next_attempt_at` (a retry, deferral, or queued manual request), and report exhausted
retries and blocked reasons. Diagnostics include running executions, worker queue
size, and concurrency limits. Preparation failures remain visible until repaired.

`scheduler.max_concurrent_servers` defaults to 4 (range 1–32).
`scheduler.poll_interval_seconds` defaults to 60 (range 1–60). Both apply after a
BSM restart. Schedule controls wake the loop immediately. Definitions and cursors
use the existing scheduler tables; execution leases and cursor metadata are stored
in their JSON state, so these additions require no new database migration.


## Pre-start backup deadlines

Backup On Start has a `timeout_seconds` setting, defaulting to 300 seconds
(5 minutes), with a maximum of 3600 seconds. This budget applies to the backup
inside the start operation; ordinary event hooks retain their existing default
limits. Settings changes take effect on the next attempt.

If the backup times out, its filesystem worker stops and temporary capture data
is cleaned up before startup proceeds. With `require_complete_backup` enabled,
startup is cancelled. Otherwise the timeout is logged and startup continues.
Explicit cancellation of the start operation, plugin unload, or an enclosing
operation deadline still cancels the operation; it is not treated as an optional backup failure.

Offline captures calculate SHA-256 hashes while copying files into private
staging storage. Inventory reuses those hashes when the staged file's size and
modification time still match. Live world captures and newly generated files
are hashed during inventory. These changes preserve the backup format and
restore checks. Optional verification after creation remains disabled by default.

## Compression and capture performance

Choose **Fast**, **Balanced**, or **Small** in Settings → Backups. Balanced is
used by default. Fast uses gzip level 1, Balanced level 6, and Small level 9;
all produce the same portable `.bsmbackup` format and retain integrity checks
and optional encryption. Older backups remain readable.

The archive writer uses bounded 1 MiB buffers. Compression builds a temporary
payload before encryption and archive publication, so capture storage must also
accommodate that compressed payload. Temporary payloads live in private staging
storage and are removed on completion, failure, or cancellation. Copies remain
sequential.

On Windows, staged files inherit the private capture directory's ACL instead
of rebuilding an ACL for each file. Other copy paths keep their explicit
permission handling; POSIX file modes remain unchanged. The completed archive
is flushed once before publication, and POSIX publication also flushes the
containing directory.

Backup listing and health read complete, atomically published archives and
catalog snapshots without taking the capture operation lock. A newly published
archive can briefly appear without its final catalog metadata; it is not shown
as verified until matching verification metadata exists. Temporary captures are
not listed. Verify, delete, restore, and metadata mutations retain their locks.

DEBUG logs and task updates distinguish compression, archive writing/encryption,
content validation, publication, archive fingerprinting, destination copies, and
retention. The capture-start log records the effective compression profile, and
DEBUG payload logs record its gzip level. Payload timings separately report
source-file open, read, and close wall time. The remaining `archive_other_ms`
includes tar processing, gzip, output I/O, metadata, and finalization; it is not a
measurement of gzip CPU time. Timings are aggregated without logging file names
or contents and require no additional file reads.


Offline captures also append copied file contents to one private, capture-local
staging file. Archive creation reads that file instead of reopening each copied
file, reducing Windows file-open overhead. Copying remains sequential. The
original staged tree remains available for validation, so this optimization
requires additional temporary space approximately equal to the copied contents,
on top of the staged tree and compressed payload. The staging file and its
in-memory index are discarded after capture, including cancellation and failure.
Live-world captures, generated settings, and files whose staged size or
modification time changed use normal file reads. The `spooled_files` DEBUG metric
shows how many archive entries used the single staging file. The backup format
and restore behavior are unchanged.


## Recovery performance and safety limits

Inspection authenticates the complete encrypted stream and checks the inventory
and file checksums without writing every contained file. Verification extracts
once and hashes each file as it is written. A recovery drill extracts once into a private directory on the destination
filesystem and flushes each file through its existing write handle before closing
it. Directory entries are then flushed on POSIX, and selected files are read back
to check their hashes. Actual restores use the same durable extraction path. It
never applies replacements to the live server. Restore comparisons reuse the
validated extracted-file hashes, while destination files are checked separately.

The existing task messages report authentication, extraction and hashing,
destination checks, durable extraction, directory flushing, checksum checks, and comparisons.
Long extraction and read-back phases publish bounded file-count updates. DEBUG
logs include worker durations without file contents or recovery keys. Import and
decrypted export retain their existing HTTP responses; their filesystem work and
cleanup run outside the event loop. No new endpoints are required.

`backups.max_files` limits all payload entries, including the manifest and
directories. `backups.max_expanded_bytes` bounds both the authenticated compressed
payload and the manifest-plus-file contents; `backups.max_archive_bytes` bounds
the final stored archive. Creation checks these limits before publication, with
early checks where source sizes are known. These checks do not enable full
verification after creation, which remains disabled by default.

Capture and extraction check available staging space before writing large amounts
of temporary data. Estimates include private staging, the sequential spool,
compressed payload, final archive, and conservative filesystem overhead. Space can
still change while an operation runs; write failures remain possible and do not
authorize replacing live data or removing the previous recovery point.

Retention requires unchanged integrity evidence and recorded requirements that
fit the current reader limits before a capture can replace older recovery points.
Older archives without recorded requirements are retained conservatively until
new capture or verification evidence is available. Invalid individual catalog
records are isolated and protected from automatic deletion; their original values
are preserved under `invalid_archives` when the catalog is next saved. Catalog
problems must not be repaired by deleting archives blindly. A failure in retention
after successful capture is reported as a maintenance warning on the created backup.

Passed recovery drills are bound to the tested archive's size and modification
time. Changing the archive invalidates that passed result. A new drill is required
to establish fresh evidence. Failed or interrupted drill status remains visible
for attention. Internal `.bsm-` paths are reserved case-insensitively, including in
full-directory archives, to protect Windows recovery storage.

Legacy and portable backup listings, archive downloads, and recovery reports do
not wait for a long recovery drill's server mutation lock. Downloads hold an open
archive handle; deletion behavior follows the host filesystem, and failures to
remove an in-use file are retained for retry. Mutations remain serialized.
Preparation workers check cancellation while walking, hashing, comparing, and
flushing. Restore commit and rollback recovery continue to finish safely before
releasing ownership. POSIX rollback flushes both affected parent directories before
recording that each entry has been restored.


### Copy and flush measurements

Long copy and flush workers update the existing task message with completed file
and byte counts at most once per second, plus start and completion updates. No
file names, contents, or keys are included. A DEBUG `Backup file work` summary
separates copy source/target opens, reads, writes, permissions, closes, and optional
hash/spool work. Flush summaries separately measure file opens, `fsync`, closes,
and POSIX directory operations. `other_ms` includes unclassified traversal and
bookkeeping. These are wall-clock measurements, not isolated CPU timings.

All replacement-file and directory durability checks remain enabled. These
measurements identify platform costs before any further optimization changes the
recovery guarantees. Disposable-server acceptance coverage checks selected-world
and settings restoration, unselected data preservation, the protected safety
archive, an actual test-process restart, and interrupted-restore rollback.
