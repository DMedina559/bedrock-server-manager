# Backup & Restore

Data loss prevention is a critical aspect of server management. Bedrock Server Manager includes a robust backup and restore system that allows you to protect your worlds and configuration files.

## Creating Backups

You can create backups manually at any time from the web interface.

### Types of Backups

*   **World Backup**: Archives the `worlds/` directory, saving all map data, player inventories, and structures.
*   **Full Backup**: Archives both the world data and all configuration files (`server.properties`, `allowlist.json`, `permissions.json`).
*   **Config Backup**: Backs up specific configuration files individually.

### How to Create a Backup

1.  Navigate to the **Backup/Restore** page for your server.
2.  **For a World Backup**: Click **Backup World Now**.
3.  **For a Full Backup**: Click **Backup All Now**.
4.  **For Config Backups**:
    *   Click the **Backup Config File...** button to expand options.
    *   Select specific files like `server.properties`, `allowlist.json`, or `permissions.json`.

**Note**: Backups are stored in the server's `backups/` directory, organized by date and type.

## Restoring Backups

If something goes wrong, you can easily restore your server to a previous state.

### Restore Process

1.  Navigate to the **Backup/Restore** page.
2.  Click **Restore**.
3.  Select the **Restore Type**:
    *   **World**: Restore map data.
    *   **Properties**: Restore `server.properties`.
    *   **Allowlist**: Restore `allowlist.json`.
    *   **Permissions**: Restore `permissions.json`.
4.  BSM will display a list of available backups for that type, showing the creation date and file size.
5.  Find the desired backup and click the **Restore** button next to it.
6.  **Confirm the warning**: Restoring will **overwrite** the current files on the server. This action cannot be undone unless you made a fresh backup just before restoring.

### Restore All

The **Restore All** function attempts to restore the most recent backup for *all* categories (World, Properties, Allowlist, Permissions). Use this with caution when performing a full server rollback.

## Automated Backups

BSM supports automated backups to ensure you never lose progress.


1.  Default behavior often includes a "Backup on Start" option to ensure a safe point before a new session begins.
2.  Another option "Backup before Update" is enabled to create a backup before applying server updates.

## Managing Backups

While the web interface allows you to create and restore backups, you may occasionally need to manage the backup files themselves (e.g., to free up disk space).

*   Backups are standard `.mcworld` or plain `json`/`properties` files.
*   They are located in the `backups/<server_name>` folder.
*   You can manually delete old backup files using a file manager or the command line if the default pruning options are insufficient.
