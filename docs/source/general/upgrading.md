# Upgrade an installation

Choose the target backend release and read its release notes before changing a working installation. Documentation for `dev` can describe unreleased behavior.

## Prepare

Record the current package versions, Python interpreter, service account, configuration/data directories and database connection. Back up the bootstrap configuration, database and required data files, plus game worlds and configuration. Preserve external plugin files and settings.

Stop the manager gracefully before replacing packages or moving storage. For containers, stop through Docker so its restart policy does not immediately relaunch the old process.

## Install and verify

Upgrade in the environment used by the service, or pull the chosen container image while preserving its mounts. Retain the same configuration directory and account permissions. Start BSM and inspect startup/migration logs, account access, server discovery and plugin status before starting game servers.

Regenerate or update API clients when contracts change. Check external plugins against typed requests, response models and event payloads. A frontend installed separately from the backend must remain within the backend's supported dependency range.

For the web-runtime changes, recreate existing service definitions so they use the updated startup and stop policies. See [runtime supervision](../extras/web_runtime.md). Review lifecycle deadlines against the supervisor's stop allowance.

## Roll back deliberately

Reinstalling an older package does not undo database migrations or world-format changes. Restore compatible storage from the prepared backup when required, using the matching application version. Test recovery separately before relying on it for production maintenance.

Use [troubleshooting](troubleshooting.md) if startup fails; preserve logs and the original backup before attempting another migration.
