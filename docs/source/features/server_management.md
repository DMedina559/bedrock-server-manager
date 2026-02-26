# Server Management

Bedrock Server Manager (BSM) provides a comprehensive set of tools to manage the lifecycle and runtime of your Minecraft Bedrock Dedicated Servers. This section covers starting, stopping, restarting, sending commands, and monitoring server resources.

## Basic Operations

The dashboard is the central hub for managing your servers. From here, you can perform basic operations on any configured server instance.

### Starting a Server

To start a server:

1.  Navigate to the **Dashboard** page.
2.  Click the **Start** button on the server card.
3.  The server status indicator will change from `Stopped` to `Starting`, and finally to `Running` once the server is fully operational.

### Stopping a Server

To stop a running server:

1.  Navigate to the **Dashboard** page.
2.  Click the **Stop** button on the server card.
3.  BSM will attempt to gracefully shut down the server.

**Graceful Shutdown**: BSM sends the `stop` command to the server console, allowing it to save chunks and player data before terminating, if that fails, it will forcibly kill the process after a timeout period.

### Restarting a Server

To restart a server:

1.  Navigate to the **Dashboard** page.
2.  Click the **Restart** button on the server card.
3.  The server will shut down and immediately start up again. This is useful for applying configuration changes or refreshing the server state.

## Console Interaction

You can send commands directly to the server console without needing SSH access to the host machine.

1.  Navigate to the **Dashboard** page.
2.  Click the **Send Command** button on the server card.
3.  A prompt will appear asking for the command.
4.  Type your command (e.g., `say Hello World`, `op <player_name>`, `gamerule doDaylightCycle false`) and click **OK**.
5.  The command is sent directly to the server.

**Note**: Do not include the leading `/` for commands sent via the console, although most commands will work with or without it.

## Resource Monitoring

The **Monitor** page provides real-time visibility into the performance of your server instances.

### Viewing Usage Stats

2.  Select the server from the dropdown menu in the web dashboard.
3.  Navigate to the **Monitor** page from the web dashboard.
3.  Real-time metrics include:
    *   **PID**: The process ID of the server instance.
    *   **CPU Usage**: Percentage of CPU cores used by the server process.
    *   **Memory Usage**: RAM consumed by the server (e.g., "350 MB").
    *   **Uptime**: How long the server has been running.
    *   **Server Log**: A live feed of the server console output, allowing you to see player activity, errors, and other events as they happen.
    *   **Quick Actions**: Buttons to start, stop, restart, or send commands to the server directly from the monitor page.

### Auto-Refresh

The monitor page automatically refreshes data periodically (typically every few seconds) to give you an up-to-date view of your infrastructure.
