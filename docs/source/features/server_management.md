# Manage running servers

Select a server in the dashboard to inspect its status, logs and resource usage. Account roles determine which management operations you can perform.

## Start, stop and restart

Start launches the Bedrock process; enabled before-start plugins can run checks, updates or backups first. Inspect the final status and logs if startup fails.

Stop requests a graceful Bedrock shutdown so the game can save data. If the process does not exit within the configured timeout, termination may be required. Restart stops and starts the server again; use it after changing properties that require a new process.

These actions control a game server. To stop BSM itself, use [web runtime shutdown](../extras/web_runtime.md).

## Console commands

Send commands through the server's console view while it is running. For example, `say Maintenance starts soon` sends a message to players. Console commands normally omit the chat command's leading `/`.

A successfully submitted command does not guarantee that Bedrock accepted its arguments. Check console output for the game's response. Commands can change worlds or player privileges; use the same care as an interactive server console.

## Monitor and maintain

Resource readings describe the running process. Logs help distinguish a process crash from a network problem or a rejected command. Review enabled autostart/update plugins before scheduling restarts, and create backups before maintenance that replaces data.

[Installation and updates](installation.md), [configuration](configuration.md) and [backups](backups.md) explain the corresponding maintenance workflows.
