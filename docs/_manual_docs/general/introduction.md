# Introduction

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

<img alt="PyPI - Version" src="https://img.shields.io/pypi/v/bedrock-server-manager?link=https%3A%2F%2Fpypi.org%2Fproject%2Fbedrock-server-manager%2F"> <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/bedrock-server-manager"> <img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dw/bedrock-server-manager"> <img alt="License" src="https://img.shields.io/github/license/dmedina559/bedrock-server-manager">


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

Certain variables can can be changed directly in the `./.config/bedrock_server_manager.json`

#### JSON Configuration File:

Provides the default configuration values for the application.

These defaults are used when a configuration file is not found or when a specific setting is missing from an existing configuration file. Paths are constructed dynamically based on the determined application data directory (see _determine_app_data_dir()).

The structure of the default configuration is as follows:

```json
{
    "config_version": 2,
    "paths": {
        "servers": "<app_data_dir>/servers",
        "content": "<app_data_dir>/content",
        "downloads": "<app_data_dir>/.downloads",
        "backups": "<app_data_dir>/backups",
        "plugins": "<app_data_dir>/plugins",
        "logs": "<app_data_dir>/.logs"
    },
    "retention": {
        "backups": 3,
        "downloads": 3,
        "logs": 3
    },
    "logging": {
        "file_level": 20,
        "cli_level": 30
    },
    "web": {
        "host": "127.0.0.1",
        "port": 11325,
        "token_expires_weeks": 4,
        "threads": 4
    },
    "custom": {}
}
```

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