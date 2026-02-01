# Server Configuration

Configuring your Bedrock server correctly is crucial for gameplay, security, and performance. BSM provides an intuitive interface to manage `server.properties`, `allowlist.json`, and `permissions.json` directly from the web UI.

## Server Properties

The **Server Properties** page allows you to modify the core configuration of the Minecraft server. This includes settings like the server name, game mode, difficulty, and port.

### Accessing Properties

1.  Select the server from the dropdown menu in the web dashboard.
2.  Navigate to the **Server Management > Configure > Properties** page.
3.  From here, you can view and edit various server settings.

### Modifying a Setting

1.  Locate the setting you wish to change.
2.  Edit the value in the input field.
    *   **Text/Number**: Type the new value.
    *   **Toggle**: Click the switch to enable or disable the option.
3.  Navigate to the bottom of the page and click **Save Properties**.
4.  **Important**: Most changes require a **Server Restart** to take effect.

## Allowlist Management

The **Allowlist** (formerly whitelist) controls which players are permitted to join your server.

**Note**: The allowlist feature requires the bedrock server must have allowlist enabled in the `server.properties` file (`allow-list=true`).

### Managing Players

1.  Select the server from the dropdown menu in the web dashboard.
2.  Navigate to the **Server Management > Configure > Allowlist** page.
2.  **Add Player**:
    *   Enter each player's Gamertag (one per line).
    *  Optionally, enable the `Ignore Player Limit` checkbox to allow these players to join even if the server is full.
    *   Click **Add**.
3.  **Remove Player**:
    *   Find the player in the list at the bottom of the page.
    *   Click the **Remove** button next to their name.

## Permissions

The **Permissions** page allows you to assign operator roles and other permission levels to players.

**Note**: Only players who have joined the server at least once will appear in the permissions list.

### Permission Levels

*   **Visitor**: Can explore but cannot interact with blocks or entities.
*   **Member**: Standard player permissions (break/place blocks).
*   **Operator**: Admin permissions (use commands, manage server).

### Managing Permissions

1.  Select the server from the dropdown menu in the web dashboard.
2.  Navigate to the **Server Management > Configure > Permissions** page.
2.  **Add/Update Player**:
    *   Find the player in the list.
    *   Select the desired permission level from the dropdown.
    *   Click **Save Permissions**.
