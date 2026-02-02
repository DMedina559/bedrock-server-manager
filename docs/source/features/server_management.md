# Server Management

Bedrock Server Manager (BSM) provides a comprehensive set of tools to manage the lifecycle and runtime of your Minecraft Bedrock Dedicated Servers. This section covers starting, stopping, restarting, sending commands, and monitoring server resources.

## Basic Operations

The dashboard is the central hub for managing your servers. From here, you can perform basic operations on any configured server instance.

### Starting a Server

To start a server:

1.  Navigate to the **Dashboard** page.
2.  Select the desired server from the dropdown menu.
3.  Click the **Start** button.
4.  The server status indicator will change from `Stopped` to `Starting`, and finally to `Running` once the server is fully operational.

### Stopping a Server

To stop a running server:

1.  Navigate to the **Dashboard** page.
2.  Select the desired server from the dropdown menu.
3.  Click the **Stop** button.
4.  BSM will attempt to gracefully shut down the server.

**Graceful Shutdown**: BSM sends the `stop` command to the server console, allowing it to save chunks and player data before terminating, if that fails, it will forcibly kill the process after a timeout period.

### Restarting a Server

To restart a server:

1.  Navigate to the **Dashboard** page.
2.  Select the desired server from the dropdown menu.
3.  Click the **Restart** button.
4.  The server will shut down and immediately start up again. This is useful for applying configuration changes or refreshing the server state.

## Console Interaction

You can send commands directly to the server console without needing SSH access to the host machine.

1.  Navigate to the **Dashboard** page.
2.  Select the desired server from the dropdown menu.
3.  Click the **Send Command** button.
4.  A prompt will appear asking for the command.
5.  Type your command (e.g., `say Hello World`, `op <player_name>`, `gamerule doDaylightCycle false`) and click **OK**.
6.  The command is sent directly to the server.

**Note**: Do not include the leading `/` for commands sent via the console, although most commands will work with or without it.

## Resource Monitoring

The **Monitor** page provides real-time visibility into the performance of your server instances.

### Viewing Usage Stats

2.  Select the server from the dropdown menu in the web dashboard.
3.  Navigate to the **Server Management > Manage Server > Monitor Usage** page from the web dashboard.
3.  Real-time metrics include:
    *   **PID**: The process ID of the server instance.
    *   **CPU Usage**: Percentage of CPU cores used by the server process.
    *   **Memory Usage**: RAM consumed by the server (e.g., "350 MB").
    *   **Uptime**: How long the server has been running.

### Auto-Refresh

The monitor page automatically refreshes data periodically (typically every few seconds) to give you an up-to-date view of your infrastructure.
