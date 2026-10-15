# Application settings and storage

Application settings control BSM as a whole. Per-server Bedrock properties are covered in [server configuration](configuration.md).

## Bootstrap configuration

Startup configuration selects the configuration directory, data directory, database URL and logging level. Resolution follows command-line options, environment variables, the bootstrap configuration file, then defaults. Supported environment variables include `BSM_CONFIG_DIR`, `BSM_DATA_DIR`, `BSM_DB_URL` and `BSM_LOG_LEVEL`.

The default configuration directory is platform-specific. Keep services, manual commands and maintenance tools pointed at the same directory. Do not assume it is a `.config` folder beside your checkout.

## Stored settings

Application and plugin settings use typed state backed by the database. Administrators can inspect and change supported settings through the management interface. Invalid values are rejected rather than silently becoming runtime configuration.

Paths select server, backup, content and download locations. Changing a path does not move existing files. Plan and back up a storage move, stop affected activity, move data deliberately, and verify permissions under the service account.

Web settings include `web.cors_origins`, a list of allowed browser origins such
as `["https://dashboard.example.com"]`. Origins must omit URL paths, credentials,
queries, and fragments. An empty list disables cross-origin access; `["*"]`
allows every origin. Same-origin access does not require a CORS entry. Changes
take effect after restarting the web server. Existing bootstrap JSON
`web.cors_origins` values are imported only when no database policy exists;
once imported, the database is authoritative and the legacy JSON entry can be
removed.

## Accounts and plugins

Administrators manage accounts and invitation tokens. Use the expiry returned for the generated invitation rather than assuming a fixed lifetime. BSM roles are separate from Bedrock player permissions; see [access and roles](../web/role_access_table.md).

Plugin settings determine optional automation. Review the [bundled plugins](default_plugins.md) and keep external plugins compatible with the installed backend.

## Lifecycle settings

Lifecycle deadlines bound request draining, managed tasks, server stops, plugin cleanup and event delivery. Increasing a deadline may also require a longer service stop allowance. Already-running synchronous plugin code cannot be forcibly cancelled by Python; overdue work can block reload until it finishes.

See [runtime and shutdown](../extras/web_runtime.md) for the cleanup order, control credentials and supervisor policies. Preserve the bootstrap configuration, database and required data files when backing up the whole installation.
