# Manage running servers

Select a server in the dashboard to inspect its status, logs and resource usage. Account roles determine which management operations you can perform.

## Start, stop and restart

Start launches the Bedrock process; enabled before-start plugins can run checks, updates or backups first. Inspect the final status and logs if startup fails.

Stop requests a graceful Bedrock shutdown so the game can save data. If the process does not exit within the configured timeout, termination may be required. Restart stops and starts the server again; use it after changing properties that require a new process.

These actions control a game server. To stop BSM itself, use [web runtime shutdown](../extras/web_runtime.md).

## Console commands

Send commands through the server's console view while it is running. For example, `say Maintenance starts soon` sends a message to players. Console commands normally omit the chat command's leading `/`.

A successfully submitted command does not guarantee that Bedrock accepted its arguments. Check console output for the game's response. Commands can change worlds or player privileges; use the same care as an interactive server console.

## Online players

Open the selected server's **Online Players** page to inspect current player sessions and the management actions available to your account. Check the selected server and player identity before acting.

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

## Monitor and maintain

Resource readings describe the running process. Logs help distinguish a process crash from a network problem or a rejected command. Review enabled autostart/update plugins before scheduling restarts, and create backups before maintenance that replaces data.

[Installation and updates](installation.md), [configuration](configuration.md) and [backups](backups.md) explain the corresponding maintenance workflows.
