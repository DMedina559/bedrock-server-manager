# Introduction

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

<img alt="PyPI - Version" src="https://img.shields.io/pypi/v/bedrock-server-manager?link=https%3A%2F%2Fpypi.org%2Fproject%2Fbedrock-server-manager%2F"> <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/bedrock-server-manager"> <img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dw/bedrock-server-manager"> <img alt="License" src="https://img.shields.io/github/license/dmedina559/bedrock-server-manager">

Bedrock Server Manager is a comprehensive python package designed for installing, managing, and maintaining Minecraft Bedrock Dedicated Servers with ease through a user-friendly web interface. It is compatible with both Linux and Windows systems.

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/docs/images/main_index.png
:alt: Web Interface
:width: 600px
:align: center
```

## Features

-   **Install New Servers**: Quickly set up a server with customizable options like version (LATEST, PREVIEW, or CUSTOM versions).
-   **Update Existing Servers**: Seamlessly download and update server files while preserving critical configuration files and backups.
-   **Backup Management**: Automatically backup worlds and configuration files, with pruning for older backups.
-   **Server Configuration**: Easily modify server properties and the allow-list interactively.
-   **Auto-Update**: Automatically update the server with a simple restart.
-   **Content Management**: Easily import .mcworld/.mcpack files into your server.
-   **Resource Monitoring**: View how much CPU and RAM your server is using.
-   **Web Server**: Manage your Minecraft servers in your browser, even if you're on mobile!
-   **Plugin Support**: Extend functionality with custom plugins that can listen to events, access the core app APIs, and trigger custom events.

---

## Quick Start Guide

### Step 1: Installation

```{note}
This app requires **Python 3.10** or later, and you will need **pip** installed.
```

First, install the main application package from PyPI:
```bash
pip install --upgrade bedrock-server-manager
```

#### (Optional) Install the API Client for CLI Management

To manage your servers from the command line, install the optional API client:
```bash
pip install --upgrade "bsm-api-client[cli]"
```
This provides the `bsm-api-client` command, which allows you to perform various tasks via the API.

> See the [Installation Guide](../extras/installation.md) for beta or development versions.

### Step 2: Configure the Web Server

To get started with the web server, you must first set these environment variables. **The web server will not start if these are not set.**

1.  **Generate Password Hash:**
    The `BEDROCK_SERVER_MANAGER_PASSWORD` variable requires a password hash, **not** plain text. Use this command to generate one:
    ```bash
    bedrock-server-manager generate-password
    ```
    Follow the prompts and copy the resulting hash.

2.  **Set Environment Variables:**
    -   `BEDROCK_SERVER_MANAGER_USERNAME`: **Required**. The plain text username for web UI and API login.
    -   `BEDROCK_SERVER_MANAGER_PASSWORD`: **Required**. The hashed password you just generated.
    -   `BEDROCK_SERVER_MANAGER_TOKEN`: **Recommended**. A long, random, secret string. If not set, API tokens will become invalid across restarts.

    > Follow your platform's documentation for setting environment variables.

### Step 3: Run the Application

To start the web server, use the following command:
```bash
bedrock-server-manager web start
```
By default, the server listens on `127.0.0.1:11325`. Once running, you can access the web interface in your browser at this address.

> See the [Web Usage Guide](../web/general.md) for more examples, like how to run the server on a different IP.

---

## Further Configuration

### Data Directory

Bedrock Server Manager uses an optional Environment Variable, `BEDROCK_SERVER_MANAGER_DATA_DIR`, to set the default config/data location. If this variable does not exist, it will default to `$HOME/bedrock-server-manager`.

The app will create its data folders in this location. This is where servers will be installed and where the app will look when managing various server aspects.

#### JSON Configuration File

Certain variables can be changed directly in the `bedrock_server_manager.json` file, located at `./.config/bedrock_server_manager.json` within your data directory. This file provides default configuration values for the application.

<details>
<summary><b>Default JSON file</b></summary>

```json
{
    "config_version": 2,
    "paths": {
        "servers": "<app_data_dir>/servers",
        "content": "<app_data_dir>/content",
        "downloads": "<app_data_dir>/.downloads",
        "backups": "<app_data_dir>/backups",
        "plugins": "<app_data_dir>/plugins",
        "themes": "<app_data_dir>/themes",
        "logs": "<app_data_dir>/.logs"
    },
    "retention": {
        "backups": 3,
        "downloads": 3,
        "logs": 3
    },
    "web": {
        "host": "127.0.0.1",
        "port": 11325,
        "token_expires_weeks": 4,
        "threads": 4
    }
}
```
</details>

## What's Next?
Bedrock Server Manager is a powerful tool for managing Minecraft Bedrock Dedicated Servers. To explore more about its capabilities, check out the following sections:

-   [Web Usage](../web/general.md): Discover how to use the web interface for server management.
-   [CLI Commands](../cli/commands.rst): View what commands are available for the core application.
-   [API Client CLI Commands](../cli/api_client_commands.rst): View what commands are available in the `bsm-api-client` package.
-   [Plugins](../plugins/introduction.md): Explore how to extend the functionality of Bedrock Server Manager with custom plugins.
-   [Changelog](../changelog.md): Stay updated with the latest changes and improvements in each release.
-   [Troubleshooting](./troubleshooting.md): Find solutions to common issues.
-   [Contributing](https://github.com/DMedina559/bedrock-server-manager/blob/main/CONTRIBUTING.md): Find out how you can contribute to the project and help improve it.
-   [License](https://github.com/DMedina559/bedrock-server-manager/blob/main/LICENSE): Understand the licensing terms under which Bedrock Server Manager is distributed.