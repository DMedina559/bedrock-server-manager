# What BSM manages

Bedrock Server Manager (BSM) installs and manages Minecraft Bedrock Dedicated Servers on Linux and Windows. It provides a browser interface, an HTTP API and plugin capabilities for server operations, configuration, backups and automation.

BSM is the manager process; each Bedrock server is a separate game process. The packaged frontend provides the browser interface, and the optional CLI client connects to the manager's API. Stopping a game server and shutting down the manager are separate actions.

## Find the right guide

- [Install BSM](../extras/installation.md) and complete [first startup](quickstart.md).
- [Install or update a game server](../features/installation.md).
- [Manage running servers](../features/server_management.md) and [configure player access](../features/configuration.md).
- [Protect worlds with backups](../features/backups.md) and [import content](../features/content_management.md).
- [Configure administration](../features/settings.md), [Docker](../extras/docker.md) or [runtime supervision](../extras/web_runtime.md).
- [Install plugins](../plugins/introduction.md) or [develop one](../developer/plugins/introduction.md).

Automatic startup, updates, notifications and other optional behaviors depend on enabled plugins and their settings. Review those policies rather than assuming every installation uses the same automation.

Use documentation matching your installed version. Review the [changelog](../changelog.md) before an upgrade, particularly when plugins or generated API clients are involved.
