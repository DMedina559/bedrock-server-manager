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

1.  Navigate to **Settings**.
2.  Locate the setting you wish to change.
3.  Update the value.
4.  Changes are auto-saved.
5.  **Reload**: If you edited the configuration, click the **Reload from File** button to refresh the application state.

## User Management

BSM supports a multi-user environment, allowing you to grant access to other team members.

### Inviting Users

New users are added via an invitation system.

1.  Navigate to the **Users** page.
2.  Locate the **Generate Registration Token** section.
3.  Select the **Role** for the new user (e.g., Admin, Moderator, User).
4.  Click **Generate Token**.
5.  A unique registration link will be generated (valid for 24 hours).
6.  Copy this link and send it to the person you wish to invite. They will be prompted to create their own username and password.

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
