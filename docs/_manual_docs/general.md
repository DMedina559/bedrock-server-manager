
<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg" alt="ICON" width="200" height="200">
</div> 

- [Bedrock Server Manager (BSM)](#bedrock-server-manager)
  - [Features](#features)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
    - [Install The Package](#install-the-package)
  - [Configuration](#configuration)
    - [Setup The Configuration](#setup-the-configuration)
      - [The following variables are configurable via json](#the-following-variables-are-configurable-via-json)
  - [Usage](#usage)
    - [Run the app](#run-the-app)
  - [Install Content](#install-content)
  - [Web Server](#web-server)
    - [Configure the Web Server](#configure-the-web-server)
      - [Environment Variables](#environment-variables)
      - [Generate Password Hash](#generate-password-hash)
      - [Hosts](#hosts)
      - [Port](#port)
      - [HTTP API](#http-api)
        - [Obtaining a JWT token](#obtaining-a-jwt-token)
        - [Using the API](#using-the-api)
      - [Examples](#examples-1)
  - [Disclaimers](#disclaimers)


* [CHANGELOG](./changelog.md)
* [PLUGINS](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/PLUGIN_API.md)
* [HTTP API](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/HTTP_API.md)
* [EXTRAS](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/EXTRAS.md)

# Bedrock Server Manager (BSM)

<img alt="PyPI - Version" src="https://img.shields.io/pypi/v/bedrock-server-manager?link=https%3A%2F%2Fpypi.org%2Fproject%2Fbedrock-server-manager%2F"> <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/bedrock-server-manager"> <img alt="License" src="https://img.shields.io/github/license/dmedina559/bedrock-server-manager">


Bedrock Server Manager is a comprehensive python package designed for installing, managing, and maintaining Minecraft Bedrock Dedicated Servers with ease, and is Linux/Windows compatable.

## Features

Install New Servers: Quickly set up a server with customizable options like version (LATEST, PREVIEW, or specific versions).

Update Existing Servers: Seamlessly download and update server files while preserving critical configuration files and backups.

Backup Management: Automatically backup worlds and configuration files, with pruning for older backups.

Server Configuration: Easily modify server properties, and allow-list interactively.

Auto-Update supported: Automatically update the server with a simple restart.

Command-Line Tools: Send game commands, start, stop, and restart servers directly from the command line.

Interactive Menu: Access a user-friendly interface to manage servers without manually typing commands.

Install/Update Content: Easily import .mcworld/.mcpack files into your server.

Automate Various Server Task: Quickly create cron/task to automate task such as backup-server or restart-server.

View Resource Usage: View how much CPU and RAM your server is using.

Web Server: Easily manage your Minecraft servers in your browser, even if you're on mobile!

Plugin Support: Extend functionality with custom plugins that can listen to events, access the core app APIs, and trigger custom events.

## Prerequisites

This app requires `Python 3.10` or later, and you will need `pip` installed

## Installation

### Install The Package:

1. Run the command 
```bash
pip install bedrock-server-manager
```
See the [EXTRAS](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/EXTRAS.md) for more information on installing stable, beta, and development versions of the app.

## Configuration

### Setup The Configuration:

bedrock-server-manager will use the Environment Variable `BEDROCK_SERVER_MANAGER_DATA_DIR` for setting the default config/data location, if this variable does not exist it will default to `$HOME/bedrock-server-manager`

Follow your platforms documentation for setting Enviroment Variables

The app will create its data folders in this location. This is where servers will be installed to and where the app will look when managing various server aspects. 

Certain variables can can be changed directly in the `./.config/script_config.json`

#### The following variables are configurable via json

* `BASE_DIR`: Directory where servers will be installed
* `CONTENT_DIR`: Directory where the app will look for addons/worlds
* `DOWNLOAD_DIR`: Directory where servers will download
* `BACKUP_DIR`: Directory where server backups will go
* `LOG_DIR`: Directory where app logs will be saved
* `BACKUP_KEEP`: How many backups to keep
* `DOWNLOAD_KEEP`: How many server downloads to keep
* `LOGS_KEEP`: How many logs to keep
* `CLI_LOG_LEVEL`: Level for CLI logging.
* `FILE_LOG_LEVEL`: Level for file logging.
* `WEB_PORT`: Port used by the web server. 11325 by default
* `TOKEN_EXPIRES_WEEKS`: How long JWT tokens are vaild for in weeks.

## Usage

<div style="text-align: left;">
    <img src="https://raw.githubusercontent.com/DMedina559/bedrock-server-manager/main/docs/images/cli_menu.png" alt="CLI Menu" width="300" height="200">
</div>

For a complete list of commands, see [CLI_COMMANDS.md](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/CLI_COMMANDS.md)

>Note: If you are using a version of the app prior to 3.3.0, you must run `bedrock-server-manager --help` to see the list of commands for your version.

### Run the app:

```bash
bedrock-server-manager <command> [options]
```
or

```bash
python -m bedrock_server_manager <command> [options] # 3.3.0 and later
```

##### Examples:

###### Open Main Menu:

```bash
bedrock-server-manager
```

###### Send Command:
```bash
bedrock-server-manager server send-command --server server_name "tell @a hello"
```

##### Export World:

```bash
bedrock-server-manager world export --server server_name_
```

##### Start the Web Server:

```bash
bedrock-server-manager web start --host 0.0.0.0 --host "::" --mode direct
```

## Plugin Suport

Bedrock Server Manager features a powerful plugin system that allows you to extend and customize its functionality. Whether you want to add new automations, integrate with other services, or introduce custom server management logic, plugins provide the framework to do so.

**Key Capabilities:**

*   **Event Hooks:** Plugins can "listen" to various events within BSM (e.g., before a server starts, after a backup completes) and execute custom code in response.
*   **API Access:** Plugins have safe access to core BSM functions, allowing them to perform actions like starting/stopping servers, sending commands, and more.
*   **Custom Events:** Plugins can define and trigger their own events, enabling complex communication and collaboration between different plugins.

**Managing Plugins:**

You can manage your plugins directly from the command line:

*   List all plugins and their status: `bedrock-server-manager plugin list`
*   Enable a plugin: `bedrock-server-manager plugin enable <plugin_name>`
*   Disable a plugin: `bedrock_server-manager plugin disable <plugin_name>`
*   Reload all plugins: `bedrock-server-manager plugin reload`
*   Trigger custom events for plugins: `bedrock-server-manager plugin trigger_event <event_name> --payload-json '{...}'`

Running `bedrock-server-manager plugin` without a subcommand will launch an interactive plugin management menu.

**Developing Plugins:**

To learn how to create your own plugins, please refer to the comprehensive:

**[Plugin Docs](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/PLUGIN_API.md)**

This documentation covers everything from creating your first plugin, understanding the `PluginBase` class, using event hooks and the plugin API, to advanced topics like custom inter-plugin events.

## Install Content:

<div style="text-align: left;">
    <img src="https://raw.githubusercontent.com/DMedina559/bedrock-server-manager/main/docs/images/cli_install_content.png" alt="Install Worlds" width="300" height="200">
</div>

Easily import addons and worlds into your servers. The app will look in the configured `CONTENT_DIR` directories for addon files.

Place .mcworld files in `CONTENT_DIR/worlds` or .mcpack/.mcaddon files in `CONTENT_DIR/addons`

Use the interactive menu to choose which file to install or use the command:

```bash
bedrock-server-manager world install --server server_name --file '/path/to/WORLD.mcworld'
```

```bash
bedrock-server-manager install-addon --server server_name --file '/path/to/ADDON.mcpack'
```

## Web Server:

<div style="text-align: left;">
    <img src="https://raw.githubusercontent.com/DMedina559/bedrock-server-manager/main/docs/images/main_index.png" alt="Main Index" width="300" height="200">
</div>

Bedrock Server Manager 3.1.0 includes a Web server you can run to easily manage your bedrock servers in your web browser, and is also mobile friendly!

The web ui has full parity with the CLI. With the web server you can:

- Install New Server
- Configure various server config files such as allowlist and permissions
- Start/Stop/Restart Bedrock server
- Update/Delete Bedrock server
- Monitor resource usage
- Schedule cron/task
- Install world/addons
- Backup and Restore all or individual files/worlds

### Configure the Web Server:

#### Environment Variables:

To get started using the web server you must first set these environment variables:

- **BEDROCK_SERVER_MANAGER_USERNAME**: Required. Plain text username for web UI and API login. **The web server will not start if this is not set**

- **BEDROCK_SERVER_MANAGER_PASSWORD**: Required. Hashed password for web UI and API login. Use the generate-password utility. **The web server will not start if this is not set**

- **BEDROCK_SERVER_MANAGER_SECRET**:   Recommended. A long, random, secret string. If not set, a temporary key is generated, and web UI sessions will not persist across restarts, and will require reauthentication.

- **BEDROCK_SERVER_MANAGER_TOKEN**:    Recommended. A long, random, secret string (different from _SECRET). If not set, a temporary key is generated, and JWT tokens used for API authentication will become invalid across restarts. **JWT tokens expire every 4 weeks by default**

Follow your platform's documentation for setting Environment Variables

#### Generate Password Hash:

For the web server to start you must first set the BEDROCK_SERVER_MANAGER_PASSWORD environment variable

This must be set to the password hash and NOT the plain text password

Use the following command to generate a password:

```bash
bedrock-server-manager generate-password
```
Follow the on-screen prompt to hash your password

#### Hosts:

By Default Bedrock Server Manager will only listen to local host only interfaces `127.0.0.1` and `[::1]`

To change which host to listen to start the web server with the specified host

Example: specify local host only ipv4 and ipv6:

```bash
bedrock-server-manager web start --host 127.0.0.1 --host "::1"
```

Example: specify all ipv4 and ipv6 addresses:

```bash
bedrock-server-manager web start --host 0.0.0.0 --host "::"
```

#### Port:

By default Bedrock Server Manager will use port `11325`. This can be change in script_config.json

#### HTTP API:

An HTTP API is provided allowing tools like `curl` or `Invoke-RestMethod` to interact with server.

Before using the API, ensure the following environment variables are set on the system running the app:

- `BEDROCK_SERVER_MANAGER_TOKEN`: **REQUIRED** for token persistence across server restarts
- `BEDROCK_SERVER_MANAGER_USERNAME`: The username for API login.
- `BEDROCK_SERVER_MANAGER_PASSWORD`: The hashed password for API login

##### Obtaining a JWT token:

The API endpoints require authentication using a JSON Web Token (JWT).
How: Obtain a token by sending a POST request to the `/api/login` endpoint.
Request Body: Include a JSON payload with username and password keys, matching the values set in the environment variables.

```
{
    "username": "username",
    "password": "password"
}
```

Response: On success, the API returns a JSON object containing the access_token:
```
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

Tokens expiration is configurable via `script_config.json` (default: 4 weeks).

###### `curl` Example (Bash):

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"username": "your_username", "password": "your_password"}' \
     http://<your-manager-host>:<port>/api/login
```

###### PowerShell Example:

```powershell
$body = @{ username = 'your_username'; password = 'your_password' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/login" -Body $body -ContentType 'application/json'
```

##### Using the API

Endpoints requiring authentication will need the obtained access_token included  in the Authorization header of your requests:

```
"Authorization: Bearer YOUR_JWT_TOKEN"
```

For requests sending data (like POST or PUT), set the Content-Type header to `application/json`.

#### Examples:

- Start server:

###### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/stop
```

###### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/stop" -Headers $headers
```

- Send Command:

###### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"command": "say Hello from API!"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/send_command
```

###### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ command = 'say Hello from API!' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/send_command" -Headers $headers -Body $body
```

For a complete list of endpoints see the [HTTP API Documentation](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/HTTP_API.md).

All documentation can also be found in the web server's footer `Docs` link.

## Disclaimers:

### Platform Differences:
- Windows suppport has the following limitations such as:
 - No attach to console support
 - No service integration

### Tested on these systems:
- Debian 12 (bookworm)
- Ubuntu 24.04
- Windows 11 24H2
- WSL2
