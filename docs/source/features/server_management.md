# Manage running servers

Select a server in the dashboard to inspect its status, logs and resource usage. Account roles determine which management operations you can perform.

## Start, stop and restart

Start launches the Bedrock process; enabled before-start plugins can run checks, updates or backups first. A successful start response confirms process spawn, while the server remains `STARTING` until BDS reports readiness. Startup timeout and early exit are visible failures. Inspect the final status and logs if startup fails.

Stop requests a graceful Bedrock shutdown so the game can save data. If the process does not exit within the configured timeout, termination may be required. Restart stops and starts the server again; use it after changing properties that require a new process.

These actions control a game server. To stop BSM itself, use [web runtime shutdown](../extras/web_runtime.md).

## Console commands

Send commands through the server's console view while it is running. For example, `say Maintenance starts soon` sends a message to players. Console commands normally omit the chat command's leading `/`.

Commands must be a single line without control characters and may contain at most 64 KiB of UTF-8 text. Delivery has a bounded deadline; a timeout can mean delivery is uncertain, so do not blindly resend a non-idempotent command. A successfully submitted command does not guarantee that Bedrock accepted its arguments. Check console output for the game's response. Commands can change worlds or player privileges; use the same care as an interactive server console.

## Online players

Open the selected server's **Online Players** page to inspect current player sessions and the management actions available to your account. Owned servers update presence from the live output stream; identities are retained for retry when the database is unavailable. Ban enforcement reacts to observed connections and committed ban changes. Check the selected server and player identity before acting.

```{figure} ../../images/web_online_players.png
:alt: Online Players page showing a connected player and available management actions
:width: 600px
:align: center

Inspect connected players for the selected server.
```

### Ban an online player

The player's **Ban** action opens a confirmation dialog with an optional reason. Review the selected player before confirming. Stored bans can be inspected separately under [Access Control](configuration.md#server-bans).

```{figure} ../../images/web_ban_online_player.png
:alt: Ban player confirmation dialog with an optional reason field
:width: 600px
:align: center

Confirm the intended player and optionally record a reason for the ban.
```

## Monitor, logs, and server removal

Resource readings describe the running process. Logs help distinguish a process crash from a network problem or a rejected command:

- **Server console logs (`logs:read`):** View live and recent output for a specific server on its dashboard or via `GET /api/logs/history?source=server&server_name=<name>` and the `server_log:<server_name>` WebSocket topic.
- **Application logs (`logs:read_application`):** Administrators can inspect BSM's own application logs via `GET /api/logs/history?source=application`, the `app_log` WebSocket topic, or locally with `bedrock-server-manager logs --app`.
- **Delete a server (`servers:delete`):** Administrators can permanently remove a server installation and its server-specific configuration (`DELETE /api/server/{server_name}/delete`). Because deletion is irreversible, it requires recent authentication step-up verification (`X-BSM-Recent-Auth: required`) and cannot be delegated to integration tokens.

Review enabled autostart/update plugins before scheduling restarts, and create backups before maintenance that replaces data.

[Installation and updates](installation.md), [configuration](configuration.md), [backups](backups.md), and [scheduled tasks](scheduler.md) explain the corresponding maintenance workflows.


## Process ownership and recovery

BSM owns the console pipes of processes it starts. One asynchronous consumer captures
merged stdout/stderr, updates readiness/player presence, and feeds live backup
responses. Slow database writes, plugins, and console viewers do not run in that
consumer. Output logs are persisted separately and remain available as history.

A surviving process recovered after BSM loses its handles stays outside lifecycle
monitoring and automatic restart. Its console, live output, readiness and current
player presence cannot be reconstructed from old logs. Diagnostics and summary
capabilities distinguish that condition from an owned server. Explicit stop/start
restores full ownership; terminating a recovered process is not a graceful console stop.

If BSM crashes while it owns a pipe, continued output capture is not guaranteed.
An output integrity or persistence failure is reported and initiates controlled
shutdown rather than allowing unbounded buffers or silently blocking BDS.

Live backups use generation-bound `save hold`/`save query`/`save resume` sessions.
A complete response frame is required before copying; failures and cancellation
attempt a bounded resume of the same process generation. Live backup cannot run on
a recovered process without console control. Offline-only maintenance requires a
fresh verified stopped decision, including when orphan adoption is disabled.

## Process inspection and live output waits

`GET /api/server/{server_name}/process` returns process ownership, generation,
readiness, and command availability. Its dedicated response groups output pressure
and errors under `output`, ban enforcement under `bans`, and exit evidence under
`exit`. It requires `servers:inspect` and access to that server. The server summary
continues to describe status, version, and player presence; resource usage remains
available through the existing `process_info` endpoint.

Plugins can use `server.get_process` for the same inspection and
`server.wait_for_log` to wait for one matching live output line. Log waits require
`logs:read`. By default they match future output only. For replay, pass
`after_sequence` together with the `generation` from the previous response. A
mismatched generation or a cursor older than the retained window raises an error;
the function does not silently skip missing history. Replay retains at most 256
lines and 1 MiB per process. Waits end on a match, timeout, process exit, or plugin
unload. Exact matches include the full output line, including any BDS prefix.

Recovered survivors have no live pipe, so live output waits and console commands
remain unavailable until stop/start. They are not added to lifecycle monitoring
or automatic restart.
