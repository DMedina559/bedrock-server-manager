# Use the web interface

Start the [web host](../general/quickstart.md), open its configured address and sign in. The dashboard groups server status and management actions; available actions depend on your account role.

## Manage a server

Select a server to inspect its status, console, properties, player access, content and backups. Start or stop it from its management view. Follow task status for operations that continue in the background; an accepted request is not proof that installation, backup or restoration finished successfully.

Changes to Bedrock properties commonly require a server restart. Back up the world before importing content or performing destructive operations. See [server management](../features/server_management.md) and [backup and restore](../features/backups.md).

## Manage the installation

Administrators manage accounts, application settings and plugins. BSM account roles control access to the manager; Minecraft player permissions are configured separately for each Bedrock server.

Stopping a Bedrock server leaves the web host running. Shutting down the web runtime stops the manager and runs application cleanup; see [graceful shutdown](../extras/web_runtime.md).

For integrations, use the [HTTP API](../extras/http_api.md) and [WebSocket guide](../extras/websockets.md). For appearance options, see [theming](theming.md).
