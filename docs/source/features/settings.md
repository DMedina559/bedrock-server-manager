# Application Settings

Beyond managing individual servers, Bedrock Server Manager has global settings to control the application itself, manage users, and handle plugins.

## Global Settings

The **Settings** page controls how BSM behaves.

### Key Categories

*   **Paths**: Defines where servers, backups, content, and downloads are stored on the host machine.
    *   *Note: Changing paths requires moving existing data manually.*
*   **Security**: Settings related to token timeouts and authentication.
*   **System**: Logging levels and other backend behaviors.

### Modifying Settings

1.  Navigate to **BSM Settings**.
2.  Locate the setting you wish to change.
3.  Update the value.
4.  Changes are auto-saved.
5.  **Reload**: If you edited the configuration, click the **Reload from File** button to refresh the application state.

**Note**: You can also add custom settings here that may be used by plugins. Custom keys will automatically be saved under the `custom` tree.

## Runtime lifecycle

The authenticated `/api/health` endpoint reports the runtime phase (`starting`,
`ready`, `stopping`, `stopped`, or `failed`) alongside database, state, and metrics
checks. The overview health badge displays these results.

Lifecycle deadlines are configured through **BSM Settings**. Values are seconds;
request draining applies when the web server next starts.

| Setting | Default | Purpose |
| --- | ---: | --- |
| `lifecycle.startup_timeout_seconds` | 30 | Deadline for each startup stage |
| `lifecycle.shutdown_timeout_seconds` | 15 | Deadline for each shutdown stage |
| `lifecycle.task_drain_timeout_seconds` | 30 | Time for managed operations to finish before cancellation |
| `lifecycle.plugin_timeout_seconds` | 10 | Deadline for plugin unload hooks and router cleanup |
| `lifecycle.cancellation_grace_seconds` | 2 | Additional time for overdue work to handle cancellation |
| `lifecycle.request_drain_timeout_seconds` | 10 | Uvicorn request draining before application cleanup |

Observers stop before operations drain. Server stop hooks run before plugins
unload; websockets close before state flush and database disposal. A failed stage
is logged with its name and elapsed time, and remaining cleanup still runs.
Startup failure rolls back components that were started and preserves the original
error. Repeated shutdown calls reuse the same cleanup result.

Plugins must cooperate with cancellation. Python cannot forcibly stop synchronous
plugin code already running in a worker thread. If overdue lifecycle work remains,
context reload is blocked until that work finishes.

## User Management

BSM supports a multi-user environment, allowing you to grant access to other team members.

### Inviting Users

New users are added via an invitation system.

1.  Navigate to the **Users** page.
2.  Click the **Invite User** button.
3.  Select the **Role** for the new user (e.g., Admin, Moderator, User).
4.  Click **Generate Token**.
5.  A unique registration link will be generated (valid for 24 hours).
6.  Copy this link and send it to the person you wish to invite. They will be prompted to create their own username and password.

**Warning**: The registration link will only be shown once. If you lose it, you will need to generate a new one.

### User Roles

*   **Admin**: Has full access to the system, including managing other users, installing plugins, and changing global settings.
*   **Moderator**: Typically has access to manage servers (Start/Stop, Backups) but cannot alter global system settings or manage other users.
*   **User**: Usually has read-only access to view server statuses and data without making changes.

### Managing Existing Users

Admins can manage existing accounts from the user table:

*   **Change Role**: Update a user from Moderator to Admin (or vice versa) using the dropdown.
*   **Disable/Enable**: Temporarily revoke access without deleting the account.
*   **Delete**: Permanently remove the user account.

### The "One Admin" Rule

To prevent the system from becoming inaccessible, BSM enforces a strict safety requirement:

*   **You cannot disable, delete, or demote the last active Administrator.**
*   If you wish to remove the current admin, you must first promote another user to the Admin role.

## Plugin Management

Plugins extend the functionality of BSM.

### Managing Plugins

1.  Navigate to the **Plugins** page.
2.  **View**: See a list of installed plugins and their versions.
3.  **Enable/Disable**: Toggle the switch next to a plugin to turn it on or off.
    *   *Note*: Disabling a plugin prevents it from loading on the next server restart.
4.  **Reload**: Click **Reload Plugins** to apply changes.

### Installing Plugins

1.  Download a BSM plugin.
2.  Place it in the `plugins/` directory of your BSM installation.
3.  Go to the **Plugins** page.
4.  Enable the new plugin.

## Global Player Management

The **Players** page provides a view of all players that have been discovered across all server instances. This list is used for permission management.

### Manually Adding Players

If a player has not yet joined any server, you can add them manually:

**Note**: You must know the player's exact Gamertag and XUID to add them manually. This information can be obtained through third-party services.

1.  Navigate to the **Players** page.
2.  Enter the player's Gamertag and XUID in a <gamertag1>:<xuid1>,<gamertag2>:<xuid2>,... format.
3.  Click **+ Add/Update**.

### Trigering Player Scans

BSM automatically scans for players when a server starts, but you can also trigger a manual scan:

1.  Navigate to the **Players** page.
1.  Click the **Scan Logs** button to refresh the list of players who have joined any server at least once (or are currently online).

## Metrics sampling

`monitoring.app_metrics_interval_sec` controls application and system sampling.
`monitoring.bedrock_metrics_interval_sec` controls server monitor broadcasts.
Both default to 3 seconds and accept whole seconds from 1 to 3600. Changes take
effect on the next monitoring cycle; an existing sleep finishes at its previous
interval. Process discovery and player checks retain their separate intervals.
