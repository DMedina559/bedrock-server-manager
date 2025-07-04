# Introduction

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

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

### Install/Update The Package:

1. Run the command 
```bash
pip install --upgrade bedrock-server-manager
```
See the [Installation](../extras/installation.md) documentation for more information on installing development versions of the app.

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

### Run the app:

```bash
bedrock-server-manager <command> [options]
```
or

```bash
python -m bedrock_server_manager <command> [options] # 3.3.0 and later
```

See the [CLI Usage](cli_general.md) for example on how to run the cli app.

See the [Web Usage](web_general.md) for example on how to run the web server.