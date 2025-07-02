# Bedrock Server Manager - Changelog

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```

## 3.5.0

1.  **Windows Service**:
    *   Windows service has the following considerations:
        *   You must use the `sc.exe` command to start/stop the services (`bedrock-server_name`/`BedrockServerManagerWebUI`).
        *   A BSM session cannot be opened with the `bedrock-server-manager` / `python -m bedrock_server_manager` command while any services are running. All BSM services must be stopped first.
        *   Services will not run if you have a BSM session already open, but multiple services can be started/stopped simultaneously.
        *   After creating a service, you must open the Services app (`services.msc`) and change the service's "Log On As" account from "Local System" to your local Windows user account.
        *   Requires an administrator account:
            *   You can run BSM with the `sudo` command on recent versions of Windows. See [Microsoft Sudo for Windows documentation](https://learn.microsoft.com/en-us/windows/advanced-settings/sudo/).
            *   Services can only be created through the BSM CLI (when run as admin). To start/stop a Bedrock server service, use the Web UI (only if the UI itself is running as a service) or the `sc.exe` command.
            *   It is recommended to create a web service first, run it via the Windows Services app, and then use the Web UI to easily manage your Bedrock server services.
2.  **Web server as a service**:
    *   Create a system service (Systemd on Linux / Windows Service).
    *   On Linux, you'll need to manually create an environment file with your BSM environment variables and add the `EnvironmentFile=` line to your systemd file.
    *   The `host` will be read from the JSON config file.
3.  **Config JSON migrations**:
    *   The global `script_config.json` has been renamed to `bedrock_server_manager.json`.
    *   Global settings have been migrated to a new nested format. A backup will be created, and an auto-migration will be attempted.
    *   Server config JSONs have been migrated to a new nested format. Auto-migration will be attempted, and any custom config options will be moved to a nested `custom` section.
    *   Added `web_server_host` to config. If the web server is started without a host argument, it will read from the JSON file.
    *   `BASE_DIR` has been migrated to `paths.servers`.
4.  **Threaded routes**:
    *   API routes for `update`, `start`, `stop`, and more have been converted to threaded operations for better responsiveness.
5.  **New plugin APIs**:
    *   APIs to read global and server configurations.
    *   API to set custom server configurations.
6.  Fixed world icon API route path typo: `word` -> `world`.
7.  Plugin Event: The `before_server_stop` event no longer uses the `mode` variable.
8.  Added a settings menu to the Web UI.
    ```{note}
    Not all settings (like web host/port) will be reloaded on the fly. These require a full application restart to take effect.
    ```

## 3.4.1

1.  Fixed settings target version for new server installations.
2.  For simplicity, documentation has been removed from the web server and moved to the repository's `/docs` folder.

## 3.4.0

```{warning}
STOP SERVERS BEFORE UPDATING
```

1.  **BREAKING CHANGE**: Linux `systemd` service files have been changed.
    *   You must reconfigure autostart (`autostart --reconfigure`) to update your `systemd` service files.
    *   This is due to the service `type` being changed from `forking` to `simple`.
    *   BSM now directly manages the `bedrock_server` process, and `screen` has been removed as a dependency. You can uninstall it with `sudo apt remove screen`.
    *   A note to Linux users: I apologize for the repeated `systemd` reconfigurations, but this should be the last time!

2.  **The biggest feature since the web server: PLUGINS!**
    *   Plugins are a new way to extend BSM's functionality.
    *   Install plugins by placing the `.py` file in the plugins folder (e.g., `~/bedrock-server-manager/plugins`).
    *   Enable/disable plugins in `plugins.json` located in the config directory (e.g., `~/bedrock-server-manager/.config`). Plugins are disabled by default.
    *   See the [Plugin Documentation](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/PLUGIN_DOC.md) for details.
    *   See [default plugins](https://github.com/DMedina559/bedrock-server-manager/tree/main/src/bedrock_server_manager/plugins/default) for examples.
    *   Added a `plugin` command to the CLI. See the updated [CLI Commands](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/CLI_COMMANDS.md).
    *   Added plugin management to the CLI and Web UI.
    *   Default plugins are included and can be enabled, disabled, or overridden.
    *   A custom event system allows plugins to communicate with each other and external sources.

3.  **BREAKING CHANGE**: Removed `/restore/all` route. This is now part of the `/restore/action` route, where `all` is a type parameter in the JSON body.

4.  **BREAKING CHANGE**: Removed `/world_name` route. Use the get properties route instead.

5.  Changed `/backups/list/` to `/backup/list/`.

6.  Optimized various HTML routes. Pages now render faster, with data being pulled dynamically via JavaScript. The servers table in the Web UI updates automatically without a page refresh.

7.  Improved resource usage monitoring by refactoring it into a generic `ResourceMonitor` class.

8.  Improved filesystem functions by using `threading.Lock` to prevent race conditions.

## 3.3.1

1.  Fixed panorama display in the Web UI.
2.  Fixed server process handling in the Web API.
3.  Fixed task command execution in the Web UI.

## 3.3.0

```{caution}
**MAJOR BREAKING CHANGES - READ FULL CHANGELOG BEFORE UPDATING**
```
```{warning}
**STOP SERVERS BEFORE UPDATING**

Start/Stop methods have been revamped. If you update before stopping your servers, you may need to manually terminate the running `bedrock_server` processes.
```

1.  **Revamped all CLI modules**: Any scripts or scheduled tasks using the old CLI commands must be recreated.
    *   See the updated `CLI_COMMANDS.md` for the new command structure.
    *   The CLI has been modernized using the `click` and `questionary` modules for a better interactive experience.
2.  **Changed allowlist remove player route** to `/api/server/{server_name}/allowlist/remove`.
3.  **Revamped start server actions**:
    *   **Windows**: Starting a server now creates a named pipe for sending commands. The `-m`/`--mode` flag controls behavior (`detached` for background, `direct` for foreground).
    *   **Linux**: The `start` command now incorporates `systemd` logic. The `-m`/`--mode` flag controls behavior (`detached` tries `systemctl` first, `direct` uses `screen`). You must recreate your `systemd` service files.
4.  Added `reset-world` action to delete a server's world folder (available in CLI and Web UI).
5.  Added command sending for actions like shutdown messages and reloading configurations.
6.  Application can now be run as a module with `python -m bedrock_server_manager <command>`.
7.  Changed `list-backups` `backup-type` from 'config' to ‘allowlist’, ‘properties’, or ‘permissions’.
8.  CLI and File log levels now have separate configuration values (`CLI_LOG_LEVEL`, `FILE_LOG_LEVEL`).
9.  Fixed `stop-web-server` bug where it could kill the wrong process.
10. Removed getting started guides and other extra content from the web server.
11. Refactored core functions and classes (`BedrockServerManager`, `BedrockServer`, `BedrockDownloader`) for better structure and capabilities.
12. Migrated task schedulers to their own classes to reduce redundant logic.
13. General code cleanup, file reorganization, and removal of redundant functions.

## 3.2.5

1.  Fixed the server download function to use the updated Minecraft website URL.

## 3.2.4

1.  Fixed the `restart-server` command in the CLI.

## 3.2.3

1.  Added `/api/server/{server_name}/backups/list/{type}` route.
2.  Added `/api/content/worlds` route.
3.  Added `/api/content/addons` route.
4.  Added `/api/players/get` route.
5.  Added `/api/players/add` route.
6.  Added `/api/server/{server_name}/permissions_data` route.
7.  File/folder paths for HTTP restore and prune APIs must now be relative.
8.  Routes like `/api/servers/{server_name}/` are now `/api/server/{server_name}/`.
9.  Fixed passing the `host` argument to the web server.

## 3.2.2

1.  Fixed wrong module being used for the "read server properties" route.

## 3.2.1

1.  Added `/api/info` route.
2.  Added `/api/server/{server_name}/read_properties` route.
3.  The server is now stopped before exporting a world.

## 3.2.0

1.  Added "export world" functionality to the Web UI. The export now goes to the content folder.
2.  Added "remove player from allowlist" to the Web UI and CLI.
3.  Added a command blacklist for sensitive commands like `stop`.
4.  Added more splash text.

## 3.1.4

1.  Revised HTTP docs included with the web server.
2.  Added `/api/servers` endpoint to list all servers and their status.

## 3.1.3

1.  Revised docs included with the web server.

## 3.1.2

1.  Fixed various JavaScript, allowlist, backup, and session token issues in the Web UI.

## 3.1.1

1.  Fixed missing assets (JS/images) for the web server.
2.  Added missing `generate-password` command.
3.  Fixed `manage-script-config` command.

## 3.1.0

1.  **Added Web Server**:
    *   Requires environment variables for configuration: `BEDROCK_SERVER_MANAGER_USERNAME`, `BEDROCK_SERVER_MANAGER_PASSWORD` (hashed), `BEDROCK_SERVER_MANAGER_SECRET`, and `BEDROCK_SERVER_MANAGER_TOKEN`.
    *   It is strongly recommended to run this behind a reverse proxy (e.g., NGINX, Caddy).
    *   Features a mobile-friendly UI and customizable panorama.
2.  Added `generate-password` command to create password hashes.
3.  Added `start-web-server` command with `direct` and `detached` modes.
4.  Added `stop-web-server` command.
5.  Refactored CLI and handler code into new `cli`/`api` modules.
6.  Added more detailed logging and documentation throughout the codebase.
7.  Added splash text to the CLI Main Menu.
8.  **SEMI-BREAKING CHANGE**: Changed the data directory structure. You may need to update your environment variable path if upgrading from older 3.0 versions.

## 3.0.3

1.  Fixed resource usage monitor on Linux.
2.  Fixed systemd enable/disable functionality on Linux.

## 3.0.2

1.  Fixed `EXPATH` variable in the Linux scheduler.
2.  Fixed "Modify Windows Task" functionality.

## 3.0.1

1.  Refactored the CLI to use a new `handlers` module.
2.  Refactored settings into a class-based structure.
3.  Fixed logger variables.
4.  [WIP] Initial support for sending commands on Windows (requires `pywin32`).

## 3.0.0

1.  **BREAKING CHANGE**: Completely refactored from a single `.py` script to a proper Pip package. Installation and updates are now done via `pip`.
2.  Use the `BEDROCK_SERVER_MANAGER_DATA_DIR` environment variable to set the data location.
3.  Logging was refactored to use Python's standard `logging` module, and functions now raise exceptions instead of returning error codes.
4.  Removed `windows-start`/`stop` commands.
5.  Added several new commands and new configuration variables to `script_config.json`.