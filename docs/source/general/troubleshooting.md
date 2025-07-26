# Troubleshooting

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```

When you encounter an issue, please follow these steps to diagnose and resolve the problem. Following this guide helps you solve the issue quickly and ensures you have all the necessary information if you need to file a bug report.

## Initial Checks & Common Fixes

Start with these simple steps, as they resolve many common problems.

### 1. Update to the Latest Version

The issue you're facing may have already been fixed in a newer release. Ensure both the Bedrock Server Manager and the `bsm-api-client` (if you use it) are up to date.

You can check your version in the BSM web UI and compare it with the [latest release on GitHub](https://github.com/DMedina559/bedrock-server-manager/releases/latest).

### 1.1. Check the Changelog for Breaking Changes

**If you recently upated your BSM instance, read the changelog!**

Major updates can introduce "breaking changes" that alter how BSM works. Before going further, review the changelog for the version you just installed.

```{tip} 
The changelog often contains important warnings and instructions on how to migrate your setup or fix issues caused by an update. Look for BREAKING CHANGE notices relevant to your setup (e.g., Web UI, CLI, Plugins).
```

### 2. Clear Caches

Sometimes, outdated cache files can cause unexpected behavior. Run the cleanup command to clear the `__pycache__` directories.

```bash
bedrock-server-manager cleanup --cache
```

### 3. Isolate the Problem: Disable Plugins

A plugin could be the source of the issue. To check if a plugin is causing the problem, disable all plugins through the BSM web UI, restart the manager, and see if the issue persists. If the problem disappears, re-enable plugins one by one until you find the one causing the conflict.

## Gathering More Information

If the initial steps don't resolve the issue, the next step is to gather more detailed logs.

### 4. Set Log Level to Debug

Enabling `DEBUG` level logging provides detailed operational information that is crucial for diagnosing complex problems.

1.  Go to **Settings** in the BSM web UI.
2.  Find the **Log Level** setting and change it to `DEBUG`.
3.  Save the settings and restart the Bedrock Server Manager.
4.  Reproduce the issue. The `.logs/bedrock_server_manager.log` file will now contain detailed trace information.

## Reporting an Issue

If you've followed the steps above and are confident you've found a new bug, we encourage you to report it.

### 5. Search for Open Issues

Before creating a new report, please [**search the open issues**](https://github.com/DMedina559/bedrock-server-manager/issues) on GitHub to see if someone has already reported the same problem. If you find a similar issue, you can add any additional information you've gathered to the existing thread.

### 6. Create a New Bug Report

If no existing issue describes your problem, please [**open a new bug report**](https://github.com/DMedina559/bedrock-server-manager/issues/new/choose).

When filing a report, be sure to:
*   **Use the Bug Report template.** It is structured to provide all the information we need.
*   **Provide a clear and concise title.**
*   **Include detailed steps** to reproduce the bug.
*   **Attach relevant logs.** Copy and paste the debug logs gathered in Step 4. Please remove any sensitive information before posting.

## For Developers

### Consider Contributing a Fix

If you are a developer and have identified the source of the bug, consider contributing a fix! Pull requests are always welcome. Fork the repository, create a new branch for your fix, and submit a pull request for review.

---

## Common Issues & Important Notes

This section contains solutions for common problems, often related to major updates.

*   **Updates and Graceful Shutdowns**: As of version 3.6.0, BSM automatically attempts to shut down all running servers and unload plugins gracefully when the main application stops. While the old advice to "stop servers before updating" is less critical now, it remains a good practice, especially if upgrading from a version before 3.6.0.
*   **Web UI Login Fails After v3.5.0 Update**: The migration from Flask to FastAPI in v3.5.0 required a new password hashing system (`bcrypt`). If you updated from a version prior to 3.5.0, **you must regenerate your password hash and auth tokens** to log in.
*   **CLI Commands Don't Work After v3.6.0 Update**: In v3.6.0, most CLI commands were moved to the `bsm-api-client` package. The core `bedrock-server-manager` package no longer handles most command-line actions directly.
    *   Install the new CLI with: `pip install bedrock-server-manager[cli]`
    *   Use the new command: `bsm-api-client <command>`

## Platform Information

### Windows Service Integration

Running BSM as a service on Windows has specific requirements:

*   **Administrator Privileges**: You must run your Command Prompt or PowerShell session **as an Administrator** to create, configure, or manage Windows services.
*   **Alternative to Services (No Admin)**: If you don't have administrative rights, you can manually create a task in the **Windows Task Scheduler** to launch the BSM web server on startup.
*   **Use Python from python.org**: It is **highly recommended** to use a Python installer from [python.org](https://www.python.org/downloads/windows/). The version from the Microsoft Store is known to cause critical file-locking issues that can prevent BSM and other Python Environments from working correctly.
*   **Set the "Log On As" Account**: A common reason services fail to start is incorrect permissions. After creating a service, go to the Services app (`services.msc`), find the service, and in its **Properties**, go to the **Log On** tab. Change "Log on as:" from "Local System account" to **"This account"** and enter your local Windows username and password. This ensures the service can access server files, backups, and content in your user directory.

### Linux Service Integration

*   **Enable Startup on Boot (`linger`)**: Services are created with the `--user` flag which only run while you are logged in. To enable your BSM service to start automatically on boot and stay running, you must enable lingering for your user account:
    ```bash
    sudo loginctl enable-linger $(whoami)
    ```
*   **Environment Variables**: `systemd` user services do not inherit environment variables from your shell (`~/.bashrc`, etc.). You must handle them manually:
    1.  Create a separate environment file (e.g., `~/.config/bsm/bsm.env`) containing your `BEDROCK_SERVER_MANAGER_*` variables.
    2.  **Secure the file.** Since this file contains sensitive credentials, restrict its permissions so that only your user account can read and write to it:
        ```bash
        chmod 600 ~/.config/bsm/bsm.env
        ```
    3.  Add the `EnvironmentFile=` directive to your `systemd` service file to load the variables.

### Tested Systems
- Debian 12 (Bookworm)
- Ubuntu 24.04
- Windows 11 24H2
- Windows Subsystem for Linux (WSL2)