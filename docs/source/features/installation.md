# Install and update game servers

Install BSM itself using the [package installation guide](../extras/installation.md). This page covers the Bedrock Dedicated Servers managed by BSM.

## Install a server

Create a server with a unique name and choose a release selector: `LATEST`, `PREVIEW`, a supported specific version, or `CUSTOM`. Preview builds may be unsuitable for existing production worlds. Availability of a specific release depends on the download source and local cache.

```{figure} ../../images/web_install_server.png
:alt: Install New Server form with a server name and Bedrock release selector
:width: 600px
:align: center

Choose a server name and release before starting installation.
```

For `CUSTOM`, put the server ZIP in the configured downloads root's `custom` directory (`<data_dir>/.downloads/custom/`) and select that archive (`GET /api/downloads/list`). Paths come from application settings (`paths.downloads`); they need not be beside your checkout. You can prune older cached release archives from `<data_dir>/.downloads/stable/` and `preview/` via `PUT /api/downloads/prune` (keeping the newest `keep` archives, or according to `retention.downloads`).

If a server directory with the chosen `server_name` already exists, installation stops and returns `status: "confirm_needed"` unless `overwrite: true` is confirmed (which deletes the existing server directory before installing).

Follow installation progress to completion, then review properties, game ports, allowlist and player permissions before starting. Each simultaneously running server needs distinct game ports. Confirm the process is running and inspect its logs before connecting.

## Update deliberately

Create a backup before updating. Select the desired release through the server's update action and follow the task result. Maintenance can stop and restart a running game server; configuration-preservation behavior is separate from your backup policy.

Review the new Bedrock version's compatibility with your world and packs. Avoid treating an older binary as a safe rollback for a world already opened by a newer release.

## Automatic startup and updates

Autostart and update-before-start are plugin-driven policies. Review the enabled plugins and the server's `autostart`/`autoupdate` settings before relying on them. A restart can trigger configured automation; it is not always just relaunching the same binary.

```{figure} ../../images/web_server_settings.png
:alt: Server Settings showing installed version, status, autostart, autoupdate and target version
:width: 600px
:align: center

Per-server manager settings control startup and update policy; they are separate from Bedrock properties.
```

See [bundled plugins](default_plugins.md), [configuration](configuration.md) and [backup and restore](backups.md).
