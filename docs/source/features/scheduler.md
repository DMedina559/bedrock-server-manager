# Schedule automated tasks

BSM includes a persistent, timezone-aware scheduler for recurring server backups, archive verification, retention pruning, server lifecycle operations, updates, console commands, world maintenance, player log scans, and plugin-provided tasks.

Configure schedules on the **Scheduler** page in the web interface or with `bsm-cli scheduler` commands. Administrator access (`scheduler:read` / `scheduler:manage`) is required to inspect, create, modify, or trigger schedules.

Treat `scheduler:manage` as privileged automation authority. Application-owned jobs
run with application authority, including console commands, updates, world resets
and maintenance, rather than the creator's other token scopes. Revoking a token
does not delete schedules it created; pause or remove unwanted schedules explicitly.
Server-restricted principals cannot manage this installation-wide scheduler.

## Create and manage schedules

1. Open **Scheduler** as an administrator and select **Add schedule**.
2. Enter a **Schedule ID** using letters, digits, underscores, dots, or hyphens (`1–100` characters, no spaces), such as `daily-survival-backup` or `nightly-restart`.
3. Select the target **Server** and choose a **Task** from the unified task registry.
4. Configure any task-specific options (rendered automatically from the task's schema).
5. Choose the daily **Time** (`HH:MM` in 24-hour format), **Timezone** (IANA region), active **Weekdays**, **Catch up missed run**, and **Stagger window (minutes)**.
6. Save the schedule. Newly created schedules start **paused** (`enabled: false`) unless explicitly enabled so you can review settings or test with **Run now** before activating recurring runs.

Schedules and bounded run history persist in the database across BSM restarts. The **Scheduler** page shows each job's target server, task type, next scheduled occurrence, active retry/deferral time, recent outcomes, and whether its task handler is currently available. A running job must finish before its schedule can be deleted.

### CLI schedule management

You can inspect and manage schedules from the command line with `bsm-cli`:

```console
bsm-cli scheduler list
bsm-cli scheduler list --server survival
bsm-cli scheduler save daily-backup -s survival --task backup:create --time 03:00 --timezone America/Los_Angeles --weekdays 0,1,2,3,4,5,6 --enabled
bsm-cli scheduler control daily-backup --action run_now
bsm-cli scheduler control daily-backup --action pause
bsm-cli scheduler control daily-backup --action resume
bsm-cli scheduler delete daily-backup --yes
```

## Built-in scheduled tasks

All built-in tasks use a `<domain>:<action>` identifier. Legacy task names `"backup"` and `"verify"` are normalized to `backup:create` and `backup:verify` with a deprecation warning.

| Task | Options | Server Lock | Behavior |
|---|---|---|---|
| `backup:create` | `encrypted` (`bool \| null`), `mode` (`"world" \| "selected" \| "full" \| null`), `components` (`list[str] \| null`) | Yes | Create a `.bsmbackup` snapshot archive. Inherits global encryption and content settings when options are omitted. Full-directory mode (`mode="full"`) requires Minecraft to be stopped when the job runs. |
| `backup:verify` | `minimum_age_hours` (`int`, `0–8760`, default `168`) | Yes | Verify unverified snapshot archives and archives whose last verification is older than `minimum_age_hours`. Does not create backups or stop Minecraft. |
| `backup:prune` | None | Yes | Prune old backups for the selected server according to configured retention policies (`retention.backups`, daily/weekly/monthly buckets, and storage budget). |
| `server:start` | None | Yes | Start the Bedrock server if it is not already running. |
| `server:stop` | None | Yes | Gracefully stop the running Bedrock server. |
| `server:restart` | None | Yes | Stop and restart the Bedrock server. |
| `server:update` | None | Yes | Check for and install Bedrock server updates (including a pre-update backup when applicable). |
| `server:send_command` | `command` (`str`, required) | No | Send a console command (without a leading `/`) to a running Bedrock server. Fails if the server is stopped. |
| `world:export` | None | Yes | Export the active server world to a `.mcworld` archive in the content Worlds directory. |
| `world:reset` | None | Yes | Delete the active server world directory so Bedrock generates a fresh world on the next start. |
| `player:scan` | None | No | Scan server logs to discover and update known player XUIDs and gamertags in the database. |
| `system:prune_downloads` | `directory` (`"stable" \| "preview" \| null`), `keep_count` (`int \| null`, `0–1000`) | No | Prune older downloaded Bedrock installer archives in the global download cache (`stable`, `preview`, or both when `directory` is omitted). |

Scheduled backups (`backup:create`) run through the standard backup pipeline, honoring event hooks, encryption defaults, optional readback verification (`backups.verify_after_create`), local retention, and external destination-copy policies. See [Back up and restore a server](backups.md) for archive contents, encryption keys, and retention details.

### Plugin-provided tasks

Plugins can register additional scheduled tasks under their own namespace (`<plugin_name>:<task>`). When enabled, plugin tasks appear alongside built-in tasks in the **Scheduler** task selector and expose their own validated option fields.

If a plugin is disabled or unloaded, its existing schedules remain saved in the database and appear as **Unavailable** on the Scheduler page. Re-enabling the plugin restores task availability without losing schedule configuration or run history. See [Scheduled tasks in plugins](../developer/plugins/scheduled_tasks.md) for authoring details.

## Timezones, daylight saving time, and staggering

Set the default application timezone in **Global Settings → General** (`general.timezone`, default `UTC`) using an IANA timezone name such as `America/Los_Angeles` or `Europe/London`. New schedules default to the application timezone when available; existing schedules keep their saved timezone until edited.

Always choose a regional IANA identifier (such as `America/Los_Angeles`) rather than a fixed abbreviation (`PST` or `PDT`). A daily `03:00` schedule continues to run at `03:00` local wall-clock time across both winter and summer:

- **Repeated hours (fall back):** When daylight saving time ends and a local hour repeats, the schedule runs once on the first occurrence (`fold=0`).
- **Skipped hours (spring forward):** When daylight saving time begins and a local wall-clock time does not exist, the occurrence shifts forward across the gap rather than being dropped.
- **Host independence:** BSM calculates UTC execution instants directly from each schedule's saved IANA region. Changing the host operating system's local timezone does not shift saved schedules.

BSM uses the `tzdata` package for portable IANA timezone resolution. If regional timezone data is unavailable in the Python environment, `UTC` schedules remain usable and diagnostics report a warning until `tzdata` is repaired and BSM is restarted.

### Staggering across servers

Each schedule includes a `stagger_minutes` window (`0–120` minutes, default `15`). When `stagger_minutes` is greater than zero, BSM adds a deterministic offset (`0` to `stagger_minutes` minutes, derived from the server name) to each occurrence. Giving multiple servers the same `03:00` schedule with a 15-minute stagger window spreads their start times predictably across `03:00–03:15` without random drift between days. Set `stagger_minutes` to `0` when a task must run at the exact minute configured.

## Execution controls

The **Scheduler** page and `bsm-cli scheduler control` provide three operational controls for each schedule:

- **Run now (`run_now`):** Queues an immediate manual execution using a distinct manual slot identity. Manual runs do not consume or shift the next calendar occurrence.
- **Pause / Resume (`pause` / `resume`):** Disables or enables future calendar claims. Pausing a schedule prevents new occurrences from starting; an execution that is already running continues to completion.
- **Retry now (`retry_now`):** Immediately schedules a fresh attempt for a failed or exhausted slot without waiting for the next calendar day.

Control requests can include the schedule's current `revision` so stale browser tabs reject conflicting edits. Accepting a control wakes the scheduler loop immediately; inspect the schedule's status and run history to confirm when the background execution finishes.

Schedule listings distinguish two timestamps:

- **`next_run_at`:** The next scheduled calendar occurrence based on `time`, `timezone`, `weekdays`, and `stagger_minutes`.
- **`next_attempt_at`:** The next queued retry, lock-contention deferral, or manual `Run now` execution time when an immediate or retry attempt is pending.

## Missed runs, retries, and concurrency

A newly created, edited, or re-enabled schedule begins with its next future occurrence. For existing enabled schedules:

- **Catch-up enabled (`catch_up: true`, default):** If BSM was stopped when a scheduled time passed, startup runs only the single most recent missed occurrence (within the lookback window) rather than replaying every missed day.
- **Catch-up disabled (`catch_up: false`):** Occurrences more than two minutes past their scheduled time are marked `skipped` (`Missed scheduled window`) rather than executed late.

`catch_up` only governs whether the first attempt of a missed occurrence starts late; once an occurrence has started, normal retry rules apply.

### Retries and interactive contention

Persisted database claims and completed-run reconciliation prevent duplicate executions for the same calendar occurrence across restarts:

- **Automatic retries:** If a task fails, BSM retries up to **3 attempts** for that occurrence using exponential backoff (5 minutes, then 15 minutes) within a 24-hour retry window. After 3 failed attempts, the slot is marked exhausted until the next occurrence or an explicit **Retry now**.
- **Interactive lock deferral:** Tasks that require exclusive server access (`requires_server_lock=True`) yield if an interactive operation (such as a manual backup, restore, or update) is already holding the server's operation lock. Similarly, `backup:verify` yields between archives if interactive work begins waiting on the lock. Deferred runs reschedule after 1 minute **without consuming one of the 3 failure attempts**.
- **Startup recovery:** If BSM crashes or is terminated while a scheduled run is in progress, startup reconciles completed artifacts (such as a finished snapshot archive for that slot) and otherwise records the interrupted attempt before scheduling any eligible retry.

### Concurrency and polling settings

Scheduled tasks run serially per server so two jobs for the same server never collide, while jobs for different servers can run in parallel up to the global concurrency limit:

| Setting | Default | Range | Purpose |
|---|---|---|---|
| `scheduler.max_concurrent_servers` | `4` | `1–32` | Maximum number of scheduled tasks executing concurrently across all servers |
| `scheduler.poll_interval_seconds` | `60` | `1–60` | Maximum interval between scheduler loop evaluations (controls and saves wake the loop immediately) |

Changes to `scheduler.max_concurrent_servers` and `scheduler.poll_interval_seconds` take effect after restarting BSM. Scheduler health, active jobs, queue depth, and recent run failures are included in application health and [diagnostics](../extras/diagnostics.md).
