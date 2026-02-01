# Default Plugins

Bedrock Server Manager comes with a set of default plugins that handle many standard lifecycle automation tasks. Most of these plugins are enabled by default, but you can disable them individually if desired, or even override them with custom plugins.

## Lifecycle Automation

These plugins automate server actions based on events like startup or shutdown.

### Autostart Servers
*   **Purpose**: Automatically starts servers that have the `autostart: true` setting enabled in their Service Configuration.
*   **Trigger**: Application startup (when the BSM Web Server itself starts).
*   **Key Behavior**: Iterates through all configured servers and boots them up if the flag is set.

### Backup on Start
*   **Purpose**: Ensures a safety backup exists before a server session begins.
*   **Trigger**: On bedrock server start (`before_server_start`).
*   **Key Behavior**: Performs a full backup of the server data. If the backup fails, the plugin logs a warning but allows the server to start (to prevent downtime loops).

### Update Before Start
*   **Purpose**: Checks for Bedrock Dedicated Server updates automatically.
*   **Trigger**: On bedrock server start (`before_server_start`).
*   **Key Behavior**: If `autoupdate: true` is set for the server, it checks Mojang's servers for a new version. If found, it updates the server binary before launching.

## Notifications & Safety

These plugins provide feedback to players and ensure smoother operations.

### Server Lifecycle Notifications
*   **Purpose**: Warns players about impending server events.
*   **Trigger**: Before major bedrock server events (`before_server_stop`, `before_delete_server_data`, `before_server_update`).
*   **Key Behavior**:
    *   **Shutdown**: Sends a "Server is stopping in X seconds..." message to the in-game chat and waits (default 10s) before killing the process.
    *   **Delete**: Sends a critical warning if data is about to be erased.

### World Operation Notifications
*   **Purpose**: Warns players about major world changes.
*   **Trigger**: Before major world operations (`before_world_export`, `before_world_import`, `before_world_reset`).
*   **Key Behavior**: Sends chat messages like "World import starting... Current world will be replaced."

### Auto Reload Config
*   **Purpose**: Hot-reloads configuration files.
*   **Trigger**: After configuration file changes (`after_allowlist_change`, `after_permission_change`).
*   **Key Behavior**: If you modify the Allowlist or Permissions via the Web Server while the server is running, this plugin automatically sends the `allowlist reload` or `permission reload` command to the server console, so changes take effect instantly.

## Content Tools

### Content Uploader
*   **Purpose**: Provides a web interface for uploading `.mcworld`, `.mcpack`, and `.mcaddon` files.
*   **Access**: Adds a new route `/content/upload`.
*   **Key Behavior**: Accepts file uploads and places them in the configured imports directory (`content/worlds` or `content/addons`), making them available for installation via the Content Management page.
