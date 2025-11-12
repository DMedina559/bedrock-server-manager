# Changelog

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```
## 3.7.0
1. Added WebSocket support
   - Various polling elements from the frontend has been replaced with WebSocket connections for real-time updates
2. BREAKING CHANGE: Removed `instances.py` module
    - Plugins and other modules should now access the `AppContext` object via dependency injection in FastAPI
3. Fixed Custom Downloads installs
4. Various dependency updates

## 3.6.3

### New Features:
1. Added `reset-password` command to reset a users password
2. Added `database upgrade` command to upgrade the database to the latest version
    - Removed `migrate database` command 
3. Added `--port` to `web start` command to override the port from config
4. Docker image now available on GitHub Container Registry (GHCR) and Docker Hub
    - Image: `ghcr.io/dmedina559/bedrock-server-manager:latest`, `dmedina559/bedrock-server-manager:latest`
    - Docs: [Docker Guide](./extras/docker.md)

### Backend Changes:
5. Add `reload` to `AppContext` and some related classes
6. Refactored WebUI js to npm build system
7. Added `build.sh` and `build.bat` scripts to build frontend and python packages


## 3.6.2

### Bug Fixes:
1. Fixed missing `AppContext` in System service creation
2. Fixed systemd environment file credentials not migrating in `old-config` command
3. Potential fix for `serverName` required error in web UI setup

## 3.6.1

### New Features:

1. Add `mcstatus`
    - Used to check online players count 
    - `player_count` is returned with `get_all_servers_data`
2. Added `TaskManager` class in web.tasks
    - Used for routers that used FastAPI's BackgroundTask
    - Durring shutdown all running background tasks will be brought to the main thread where they'll finish running or graceful shutdown

### Backend Changes:

3. Added shutdown flag to `BedrockProcessManager`
    - Raises `RuntimeError` if trying to register a server durring shutdown
5. Refactored/Removed web.templates into `AppContext`
6. Added `get_app_context` and `get_templates` to web.dependencies
7. Added `self.player_count` attribute to `BedrockServer` 

## 3.6.0

```{tip}
With version 3.6.0, the web server is now a required component and acts as the central management point for all Bedrock servers. This change simplifies process management and improves stability.
Key improvements include:
All server processes are now managed directly by the web server.
Configuration data has been migrated from JSON files to a database for better performance and reliability.
The previous backend CLI has been removed. All actions are now handled via the web interface.
These changes create a more robust and efficient platform for managing your servers.
```

### **Important Notices & Breaking Changes**

```{warning}
Stop servers before updating!
```
*   BREAKING CHANGE: Removed CLI Plugin support
*   Requires the BSM app to always be running (A System Service for the web server is recommended `bedrock-server-manager web service configure`)

*   Its recommended to run the `bedrock-server-manager migrate old-config` command after updating to 3.6.0 to ensure smooth migration
    * If you plan on using an external database, you should run the `bedrock-server-manager setup` command first before running the `bedrock-server-manager migrate old-config` command
    * After running this command you should also run the `bedrock-server-manager setup` command to ensure basic migration was successful

### **Core Architectural Changes**

*   Moved most of the CLI commands to the `bsm-api-client[cli]` package
*   Refactored most of the app away from global singletons to a passed around `AppContext` object
*   Added gracefull shutdown for BSM
    *   Shuts down all running bedrock servers
    *   Unloads all plugins
*   Web server now starts without needing any setup

### **Database and Configuration Migration**

*   Database migrations
    ```{note} 
    Using the default database has been observed to cause slow loadding times for the web server on some systems, if you experience this issue, consider using an external database such as MySQL or PostgreSQL.
    ```
    *   Migrated BSM from a JSON based config to a SQLite database
    *   Use default included `bedrock_server_manager.db` or use your own external database
    *   Automatically migrates from the old JSON config to the new database
    *   All json config files are now stored in the database
        *   This includes the global config, server configs, and plugin configs, player configs
    *   All environment variables are now stored in the database
        *   Web server environment variables are now stored in the database and are auto migrated to the database
        *   App Data Directory is now stored in a seperate json file in the users `%APPDATA%` directory (`~/.config/bedrock-server-manager` on linux, `~/AppData/local/bedrock-server-manager` on Windows)
            *   Database URL is also stored in this file
*   Added `migrate` command
    * `migrate databse` command to migrate the database to new versions as needed (for future updates)
    * `migrate old-config` command to migrate from the old JSON config (<V3.5) to the new database
        * This command will migrate the following:
            * `bedrock_server_manager.json` (global config)
            * `<server_name>_config.json` (server configs)
            * `players.json` (global player)
            * `plugins.json` (plugins)`
            * `BEDROCK_SERVER_MANAGER_DATA_DIR` (app data directory)
            * `BEDROCK_SERVER_MANAGER_USERNAME`, `BEDROCK_SERVER_MANAGER_PASSWORD`, `BEDROCK_SERVER_MANAGER_TOKEN` (web auth environment variables)
            * Bedrock Server System Services
*   Added `setup` command to setup App config
    *   Sets up the App Data Directory and database URL, Web Host and Port, system service

### **Server Management**

*   Revamped server start methods
    *   Now uses a generic process open instead of complex platform specific named pipe methods
        * This vastly improves cross platform compatibility 
    *   System Services for individual servers will no longer work, is now handled by the `autostart_plugin` during BSM startup
*   Added crash restarts
    *   Bedrock servers will now restart if they crashed

### **Multi-User and Access Control**

*   Added Multi user support with Access Control
    *   Admins can now create and manage users with different access levels
        *   Current access levels:
            *   Admin: Full access to full application
            *   Moderator: Limited to basic server management not including updates, installs, or content management
            *   User: Limited to view privileges, can only view basic data
    *   Admins can create a registration link for users to register
        *   Link is valid for 24 hours
    *   Admins can enable/disable user accounts, and change their roles
*   Themes are now user specific
    *   Each user can now have their own theme

### **System Service Improvements**

*   Improved system service support
    *   On Windows you can now enter account credentials to run the service as a specific user
    *   Added `--system` flag for linux to create a systemd service for the web server on the system level

### **Plugin and Developer Updates**

*   If you're a plugin developer with FASTAPI plugins, you should update your plugins to use the new `get_current_user`, `get_admin_user`, `get_moderator_user` dependency to ensure proper access control
*   Added the `server_lifecycle_manager` as a Plugin Method
    *   A context manager useful for plugins that need to perform actions on servers the requires the server to be stopped
*   The `get_*_instance` functions in `instances.py` have been deprecated (will be removed in 3.7.0)
    *   Instead the AppContext object (created in the CLI app) is passed around to all functions
    *   FastAPI plugins can access the `AppContext` object via `app.state.app_context`
*   Added `app_context` to the `PluginAPI` class, plugins can now access the AppContext object to access the current app state with `self.api.app_context`
    *   AppContext will be automatically passed to all plugin methods
*   Plugins are now only loaded during the web server startup, no longer during the CLI app startup

### **Other Backend Changes**

*   Various backend changes such as:
    *   Object based authentication
    *   Changes routers to use the new `get_current_user`, `get_admin_user`, `get_moderator_user` dependencies
    * Added `AppContext` object
        * This object holds the current app state such as:
            * Settings instance
            * Database instance
            * BedrockServerManager instance
            * BedrockServer instances
            * BedrockProcessManager instance
            * PluginManager instance
        *   Most API modules have been refactored to use the new AppContext object

## 3.5.7
```{tip}
Experience the new CLI before the 3.6.0 update now:

`pip install --upgrade bedrock-server-manager[cli]`

Use the `bsm-api-client` command to interact with the web server

View all commands at: [BSM API Commands](https://bedrock-server-manager.readthedocs.io/en/latest/cli/api_client_commands.html)

```

1. Added generic task manager for FastAPI background task
    - Background task now retun a task ID you can use to monitor various task such as server installs, backups and more.
    - Added `/api/tasks/status/{task_id}` for status tracking
    - If your FASTAPI plugin uses background task, consider migrating to the `bedrock_server_manager.web.tasks` functions for a consistent user experience
2. Fixed server version api endpoint
3. Improved CLI permissions menu experience
4. No longer restart server after properties change

## 3.5.6
1. Fixed allowlist remove command
2. Filter logs to only show BSM and Plugin logs
3. Minor backend changes
4. Added various tests for the CLI and Web API
5. BREAKING CHANGE: Task shceduler functionality has been removed from the CLI and Web API. 
    ```{note}
    The current task scheduler functionality will be reintroduced in a future as optiaonal plugins.
    ```

## 3.5.5
1. Hot fix for server properties path

## 3.5.4
1. FIxed custom cli/web plugins not being loaded correctly.

## 3.5.3
1. Optimzed class initialization

## 3.5.2
1. Fixed missing html for Content Upload Plugin.
2. Hardcode uvicorn workers to 1 to avoid potential conflict with flile locking and theme loading issues.

## 3.5.1
1. Fixed a bug where running the web server behind a reverse proxy was causing issues with the web UI and API routes.

## 3.5.0

```{warning}
BREAKING CHANGE: WEB USERS
If you are using the web server, you must regenerate your password hash and auth tokens.
```

```{tip}
Documentation for the Bedrock Server Manager (BSM) has been completely revamped and is now available at: 

Main:   [https://bedrock-server-manager.readthedocs.io/](https://bedrock-server-manager.readthedocs.io/)

Mirror: [https://dmedina559.github.io/bedrock-server-manager/](https://dmedina559.github.io/bedrock-server-manager/)
```

1. **CLI/WEB Plugins**: Experimental support for custom CLI and Web plugins 

    ```{important}
    When using these new plugin types that extend Bedrock Server Manager (BSM) functionality, exercise caution during installation and execution. Always ensure you understand the plugin's operations before running it.
    ```

    ```{warning}
    Plugins that add web endpoints have the potential to expose sensitive data. If you're developing such a plugin, it's highly recommended to use  the `bedrock_server_manager.web` `get_current_user` dependencies within your FastAPI routers. This helps secure your endpoints with the same authentication system the main web app uses.
    ```

    * Plugins can add custom CLI commands or entities to the CLI menu
    * Plugins can add custom web API endpoints/UI menus
    * New default plugin: Upload Content Plugin (disabled by default)
    * Support for package format plugin 
       * In addition to the standalone py file plugins, support for plugins in a python package format has been added

2.  **Windows Service**:
 
    Running Bedrock Server Manager components (Web UI, individual Bedrock Servers) as Windows Services allows them to run in the background, start automatically on boot, and be managed by the Windows Service Control Manager.

    ```{important}
    It is **highly recommended** to use a Python installation downloaded from [python.org](https://www.python.org/downloads/windows/) rather than the version available from the Microsoft Store. The Microsoft Store version of Python has been observed to cause significant file locking issues when used with Windows Services, preventing other Python scripts or applications (including new BSM CLI sessions) from running correctly, even when using virtual environments. Using the python.org installer typically avoids these specific locking problems.
    ```
    *   General Considerations:
        * Administrator Privileges: Creating, configuring, starting, and stopping Windows services requires Administrator privileges. You can achieve this by:
            * Running your Command Prompt or PowerShell as an Administrator before executing bsm commands.
            * Using the sudo command on recent versions of Windows if you have it configured.
                * See [Microsoft Sudo for Windows documentation](https://learn.microsoft.com/en-us/windows/advanced-settings/sudo/).
        * Service Account: By default, services created by BSM might be configured to run as the "Local System" account. For Bedrock servers, which often need to access user-specific paths for server files, content, and backups (e.g., in your user profile or a directory your user owns), it is usually necessary to change the service's "Log On As" account to your local Windows user account. This can be done via the Services app (services.msc) after the service has been created by BSM. This step ensures the service has the correct permissions. Failure to do this is a common cause of services not starting or functioning correctly.
3.  **Web server as a service**:
    *   Create a system service (Systemd on Linux / Windows Service).
    *   On Linux, you'll need to manually create an environment file with your BSM environment variables and add the `EnvironmentFile=` line to your systemd file.
    *   The `host` will be read from the JSON config file.
    *   On Windows, uvicorn workers will default to 1 instead of the configured settings value.
4.  **Web UI Themes**:
    *   Added support for custom themes in the Web UI.
    *   Themes can be placed in the `themes` directory.
    *   The Web UI will automatically list them in the settings menu.
    *   Various themes are available, including:
        *   `dark`
        *   `light`
        *   `red`
        *   `blue`
        *   `yellow`
        *   `green`
        *   `black`
        *   `gradient`
 
    *   The default theme is `dark` theme (original OreUI insipred).
5.  **Config JSON migrations**:
    *   The global `script_config.json` has been renamed to `bedrock_server_manager.json`.
    *   Global settings have been migrated to a new nested format. A backup will be created, and an auto-migration will be attempted.
    *   Server config JSONs have been migrated to a new nested format. Auto-migration will be attempted, and any custom config options will be moved to a nested `custom` section.
    *   Added `web_server_host` to config. If the web server is started without a host argument, it will read from the JSON file.
    *   `BASE_DIR` has been migrated to `paths.servers`.
6.  **Background Task**:
    *   API routes for `update`, `start`, `stop`, and other long running endpoints have been converted to FastAPI's BackgroundTasks for better responsiveness.
      * As a result Web APIs now instantly return a success response instead of the actual result for the task. In future versions, these endpoints will be updated to handle this.
7.  **New plugin APIs**:
    *   APIs to read global and server configurations.
    *   API to set custom global and server configurations.
8.  **Custom Bedrock Server Zips**
    *   Added support for custom Bedrock Server zips.
    *   These can be placed in the `DOWNLOAD_DIR/custom` directory.
    *   The Web/CLI UI will automatically list them in the server creation, when target version is set to `CUSTOM`.
9.  Fixed world icon API route path typo: `word` -> `world`.
10.  Plugin Event: The `before_server_stop` event no longer uses the `mode` variable.
11.  Added a settings menu to the Web UI.
    ```{note}
    Not all settings (like web host/port) will be reloaded on the fly. These require a full application restart to take effect.
    ```
12. BREAKING CHANGE: Migrated Flask to FastAPI for the Web API.
    *   This allows for better performance and more modern features.
    *   The Web UI has been updated to work with the new FastAPI routes.
    *   Always up-to-date HTTP API docs are now available in the Web UI footer `HTTP API` link or at `http(s)/bs.host.url/docs`.
      * The OpenAPI json are also available at `http(s)/bs.host.url/api/openapi.json`.
    *   Switched to `uvicorn` as the ASGI server for the Web API.
    *   Switched to `bcrypt` for password hashing in the Web API.
        * This requires you to regenerate your password hash and auth tokens.
13. BREAKING CHANGE: `/api/login` has been changed to `/auth/token`
14. Noteworthy change:
    * `/api/plugins/reload` method changed to `PUT` instead of `POST`.

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