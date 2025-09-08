# Introduction

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

<img alt="PyPI - Version" src="https://img.shields.io/pypi/v/bedrock-server-manager?label=Version&color=green">
<img alt="PyPI Downloads" src="https://static.pepy.tech/personalized-badge/bedrock-server-manager?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=YELLOW&left_text=PYPI+Installs">
<img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/dmedina559/bedrock-server-manager?label=Docker%20Pulls&color=pink">
<img alt="GitHub License" src="https://img.shields.io/github/license/dmedina559/bedrock-server-manager?label=License&color=orange">

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

Bedrock Server Manager is also available as a docker image. See the [Docker Guide](../extras/docker.md) for more information.

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

To get started with the web server, its recommended to run the setup command first:

```bash
bedrock-server-manager setup
```

This command will prompt you for the necessary configuration details, such as: 

-   **Data Directory**: The location where the application will store its data (default is `$HOME/bedrock-server-manager`).
-   **Databse URL**: The URL for the database connection (default is `sqlite:///<data_dir>/bedrock_server_manager.db`).
-   **Host**: The IP address the web server will listen on (default is `127.0.0.1`).
-   **Port**: The port the web server will use (default is `11325`).
-   **System Service**: Whether to install the web server as a system service (default is `no`).

If you choose not to run the setup command, default values will be used. This can be changed later by running the setup command.

### Step 3: Run the Application

To start the web server, use the following command:

```bash
bedrock-server-manager web start
```
By default, the server listens on `127.0.0.1:11325`. Once running, you can access the web interface in your browser at this address.

Once the server is running, a one first-time setup will be required. This includes setting up an admin user account and configuring your first bedrock server.

> See the [Web Usage Guide](../web/general.md) for more examples, like how to run the server on a different IP.

---

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