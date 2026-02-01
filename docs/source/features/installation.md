# Installation & Updates

Bedrock Server Manager streamlines the process of deploying new Bedrock Dedicated Server instances and keeping them up to date.

## Installing a New Server

You can install multiple server instances on the same machine, each with its own configuration.

### Installation Steps

1.  **Navigate to Install**: Click **Install New Server** from the dashboard sidebar or main menu.
2.  **Server Name**: Enter a unique name for your server (e.g., `Survival_World`, `Creative_Lobby`). This name will be used for the server's directory and identification.
3.  **Server Version**:
    *   **LATEST**: Automatically downloads the most recent stable version from Mojang.
    *   **PREVIEW**: Installs the latest beta/preview build for testing new features.
    *   **CUSTOM**: Allows you to select a custom server zip file that you have manually placed in the `downloads/custom` directory.
    *   **SPECIFIC VERSION**: Enter a specific released version (e.g., `1.21.114.1`, `1.21.130.22-preview`).
4.  **Install**: Click the **Install Server** button.
    *   BSM will download the server software (if not already cached) and extract it to a new directory in `servers/<server_name>`.
    *   Progress is tracked in real-time.

### Post-Installation Wizard

Once the files are installed, BSM guides you through the initial setup:

1.  **Properties**: Configure basic settings like Game Mode, Difficulty, and Port.
2.  **Allowlist**: (Optional) Add your own Gamertag so you can join immediately.
3.  **Permissions**: (Optional) Set yourself as an Operator.
4.  **Service Settings**:
    *   **Auto Start**: Check this if you want the server to start automatically when BSM starts (or the computer reboots).
    *   **Auto Update**: Check this to enable automatic updates for this instance on start up.
5.  **Finish**: Click **Save & Start Server** to boot up your new world.

## Updating Servers

Mojang frequently releases updates for Minecraft Bedrock. BSM helps you stay current without losing data.

### Manual Update

1.  On the dashboard,choose a server from the dropdown list.
2.  Click the **Update** button.
3.  BSM will:
    *   Stop the server safely (if it was running).
    *   Perform a full backup (if enabled).
    *   Download and extract the new binaries.
    *   Restore your configuration files.
    *   Restart the server (if it was running).

### Automatic Updates

If **Auto Update** is enabled for a server instance:
*   BSM checks for updates durring the bedrock server startup.
*   If a new version is detected, it will perform the update process automatically.

## Custom Versions

You may want to run an older version of the server or a specific beta build.

1.  Download the desired Bedrock Server `.zip` file manually.
2.  Place it in the `downloads/custom` folder in your BSM installation directory.
3.  During installation, select **CUSTOM** as the version.
4.  Choose your zip file from the list.
