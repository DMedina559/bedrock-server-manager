# Application settings and storage

Application settings control BSM as a whole. Per-server Bedrock properties are covered in [server configuration](configuration.md).

## Bootstrap configuration

Startup configuration selects the configuration directory, data directory, database URL, and logging level. Resolution follows command-line options, environment variables, the bootstrap configuration file (`<config_dir>/bootstrap/bedrock_server_manager.json`), then defaults. Supported environment variables include `BSM_CONFIG_DIR`, `BSM_DATA_DIR`, `BSM_DB_URL`, and `BSM_LOG_LEVEL`.

The default configuration directory is platform-specific. Keep services, manual commands, and maintenance tools pointed at the same directory. Do not assume it is a `.config` folder beside your checkout.

## Stored settings

Application and plugin settings use typed state backed by the database. Administrators can inspect and change supported settings under **Global Settings** (`GET /api/settings`, `POST /api/settings/set`). Modifying global settings requires `settings:manage` and a recent interactive login or step-up verification. Invalid values are rejected rather than silently becoming runtime configuration.

```{figure} ../../images/web_global_settings.png
:alt: Global settings showing backup retention and monitoring intervals
:width: 600px
:align: center

Application settings include retention limits and monitoring intervals.
```

### General and scheduler settings

| Setting | Default | Constraints | Purpose |
|---|---|---|---|
| `general.timezone` | `"UTC"` | Valid IANA timezone | Default timezone offered for new schedules and application time display |
| `scheduler.max_concurrent_servers` | `4` | `1–32` | Maximum concurrent scheduled tasks across servers (applies after restart) |
| `scheduler.poll_interval_seconds` | `60` | `1–60` | Maximum interval between scheduler loop checks in seconds (applies after restart) |

See [Schedule automated tasks](scheduler.md) for timezone behavior, staggering, and retry policies.

### Storage paths and retention

Paths select where BSM stores servers, backups, content templates, installer archives, external plugins, and custom CSS themes. Unless overridden, all paths resolve inside `<data_dir>` (which defaults to `<config_dir>/data`):

| Setting | Default | Purpose |
|---|---|---|
| `paths.servers` | `<data_dir>/servers` | Installed Bedrock server directories |
| `paths.backups` | `<data_dir>/backups` | Server `.bsmbackup` archives, catalogs, and database backups |
| `paths.content` | `<data_dir>/content` | Importable `worlds/` (`.mcworld`) and `addons/` (`.mcpack`, `.mcaddon`) |
| `paths.downloads` | `<data_dir>/.downloads` | Cached Bedrock installer ZIPs (`stable/`, `preview/`, `custom/`) |
| `paths.plugins` | `<data_dir>/plugins` | External Python plugin files and package directories |
| `paths.themes` | `<data_dir>/themes` | Shared custom `.css` stylesheet themes |
| `retention.backups` | `3` (`>= 0`) | Recent recovery points retained per server (`0` disables count pruning) |
| `retention.downloads` | `3` (`>= 0`) | Recent Bedrock installer archives retained per download channel |

Changing a `paths.*` setting does not move existing files on disk. Plan and back up a storage move, stop affected activity, move data deliberately, and verify permissions under the service account. For `backups.*` retention, encryption, and destination settings, see [Back up and restore a server](backups.md).

### Monitoring intervals

| Setting | Default | Constraints | Purpose |
|---|---|---|---|
| `monitoring.max_retries` | `3` | `>= 0` | Automatic restart attempts when a monitored Bedrock server crashes |
| `monitoring.process_interval_sec` | `10` | `> 0` | Interval in seconds between Bedrock process health/PID checks |
| `monitoring.player_interval_sec` | `10` | `> 0` | Interval in seconds between player log scans on running servers |
| `monitoring.app_metrics_interval_sec` | `3` | `1–3600` | Sampling interval in seconds for host and BSM application resource metrics |
| `monitoring.bedrock_metrics_interval_sec` | `3` | `1–3600` | Sampling interval in seconds for per-server Bedrock process metrics |
| `monitoring.untracked_process_interval_sec` | `5` | `1–3600` | Minimum seconds between completed negative process table scans; start/stop checks bypass this cache |
| `monitoring.recover_untracked_processes` | `true` | Boolean | Automatically scan and recover orphaned Bedrock server processes if the PID file is missing |

Process recovery verifies both the executable and working directory before rebuilding
its PID file. Multiple matching processes require manual investigation. Recovered
survivors are **not added to lifecycle monitoring or automatic restart**. BSM can
observe their PID/resources and terminate them, but cannot recover their original
console input pipe. Diagnostics report console commands and kicks as unavailable
until the server is stopped and started by BSM. BSM continues starting BDS with
direct-to-file output; recovery does not attach a new output pipe. Recovery state and scan caches are scoped
to each server handle and configuration directory.

### Web and proxy settings

| Setting | Default | Constraints | Purpose |
|---|---|---|---|
| `web.host` | `"127.0.0.1"` | Host/IP string | Default bind host saved by `bedrock-server-manager setup` |
| `web.port` | `11325` | `1–65535` | Default bind port saved by `bedrock-server-manager setup` |
| `web.cors_origins` | `[]` | Origin URLs (`http://` or `https://`) | Allowed cross-origin browser origins (`[]` disables CORS; `["*"]` allows any origin) |
| `web.forwarded_allow_ips` | `"127.0.0.1"` | IP/CIDR list or `"*"` | Trusted reverse-proxy peers allowed to supply `X-Forwarded-For` / `X-Forwarded-Proto` |
| `web.outbound_queue_limit` | `64` | `1–10000` | Maximum pending outbound WebSocket messages buffered per client connection |
| `web.token_expires_weeks` | `4` | `> 0` | Lifetime in weeks for `"remember_me"` bearer tokens |
| `web.frame_ancestors` | `null` (unset) | Optional CSP source string | When set (e.g., `"'self' https://home.example.com"`), emits `Content-Security-Policy: frame-ancestors ...`. Leave unset (`null`) to allow cross-origin framing such as Home Assistant dashboards |
| `web.csp_report_only` | `null` (unset) | Optional CSP policy string | When set to a full policy string, emits `Content-Security-Policy-Report-Only` for testing proxy or ingress policies |

`web.cors_origins` entries must omit URL paths, credentials, queries, and fragments. Same-origin browser access does not require a CORS entry. Changes to `web.cors_origins` or `web.forwarded_allow_ips` take effect after restarting the web server. Existing bootstrap JSON `web.cors_origins` values are imported only when no database policy exists; once imported, the database is authoritative and the legacy JSON entry can be removed.

### Security settings

| Setting | Default | Constraints | Purpose |
|---|---|---|---|
| `security.require_admin_mfa` | `false` | Boolean | Require all `admin` accounts to enroll TOTP MFA or a passkey before accessing administrative routes |
| `security.session_idle_hours` | `24` | `1–672` | Idle timeout in hours before an inactive browser session expires |
| `security.session_max_days` | `28` | `1–90` | Maximum lifetime in days for a browser session regardless of activity |
| `security.auth_account_attempts` | `10` | `3–100` | Failed authentication attempts per account within the rate-limit window before throttling |
| `security.auth_peer_attempts` | `60` | `10–10000` | Failed authentication attempts per client IP / IPv6 prefix within the rate-limit window |
| `security.auth_window_seconds` | `300` | `30–3600` | Sliding window in seconds for authentication rate limiting |
| `security.auth_ipv6_prefix` | `128` | `48–128` | IPv6 prefix length used to group client addresses for peer rate limiting |

Administrators manage accounts, per-server access assignments, integration tokens, and invitation links under **Users** and **Access Control**. BSM roles and permission scopes are separate from Bedrock player permissions; see [Roles, permissions, and account security](../web/role_access_table.md).

### Lifecycle, event bus, and diagnostic settings

Lifecycle deadlines bound startup, shutdown, request draining, managed tasks, server stops, plugin cleanup, and event delivery:

| Setting | Default | Constraints | Purpose |
|---|---|---|---|
| `lifecycle.startup_timeout_seconds` | `30.0` | `(0, 600]` | Deadline in seconds for each application startup stage |
| `lifecycle.shutdown_timeout_seconds` | `15.0` | `(0, 600]` | Default deadline in seconds for each application shutdown stage |
| `lifecycle.server_stop_timeout_seconds` | `10.0` | `(0, 600]` | Grace period in seconds for a Bedrock server to stop after receiving `stop` |
| `lifecycle.task_drain_timeout_seconds` | `30.0` | `(0, 600]` | Deadline in seconds to drain active background tasks during shutdown |
| `lifecycle.plugin_timeout_seconds` | `10.0` | `(0, 600]` | Deadline in seconds for plugin load/unload lifecycle callbacks |
| `lifecycle.request_drain_timeout_seconds` | `10.0` | `(0, 600]` | Deadline in seconds for in-flight HTTP requests to finish during shutdown |
| `lifecycle.cancellation_grace_seconds` | `2.0` | `(0, 30]` | Grace period in seconds after task cancellation is requested |
| `events.hook_timeout_seconds` | `120` | `(0, 3600]` | Deadline in seconds for `before_*` event hooks |
| `events.listener_timeout_seconds` | `30` | `(0, 3600]` | Deadline in seconds for `after_*` and notification event listeners |
| `events.history_limit` | `200` | `0–10000` | Maximum recent events retained in memory for diagnostics |
| `events.max_active` | `256` | `1–10000` | Maximum concurrent active event dispatches |
| `events.max_workers` | `null` | `1–10000` | Optional cap on synchronous event worker threads |
| `events.max_workers_per_owner` | `null` | `1–10000` | Optional per-plugin cap on synchronous event worker threads |
| `events.max_depth` | `32` | `1–128` | Maximum nested event emission depth before recursion is rejected |

Increasing a lifecycle deadline may also require a longer OS service stop allowance. Already-running synchronous plugin code cannot be forcibly cancelled by Python; overdue work can block reload until it finishes. See [runtime and shutdown](../extras/web_runtime.md) for the cleanup order and supervisor policies, and [diagnostics](../extras/diagnostics.md) for `diagnostics.*` retention and sampling settings.

### Custom and plugin settings

- **`custom.*`:** Stores user-defined custom global keys (`custom.<key>`) as well as plugin-declared global settings models (`custom.<plugin_name>`).
- **`plugin_settings`:** Plugin-local settings are stored in a dedicated `plugin_settings` database table and managed through `/api/plugins/{plugin_name}/settings` (**Plugins → Plugin Settings**), rather than through `POST /api/settings/set`. See [Install and manage plugins](../plugins/introduction.md) and [bundled plugins](default_plugins.md).

## Directory layout and private credentials

### Configuration root (`<config_dir>`)

The `--config-dir` option (or `BSM_CONFIG_DIR`) identifies BSM's configuration root:

- `<config_dir>/bootstrap/bedrock_server_manager.json` — Bootstrap JSON configuration (`data_dir`, `db_url`, `logging_level`).
- `<config_dir>/db/` — Default SQLite database directory (`bedrock_server_manager.db`) for new installations.
- `<config_dir>/logs/` — Application logs and `<config_dir>/logs/servers/<server_name>/` for per-server process logs.
- `<config_dir>/runtime/` — Web runtime PID, lock, and shutdown control files (`web_server.pid`, `web_server.lock`, `web_server.control.json`), plus `<config_dir>/runtime/servers/<server_name>/` for server PID files.
- `<config_dir>/credentials/` — Restricted private key directory (`backup.key` for backup encryption, `jwt.key` for session signing, and `mfa.key` for TOTP secret encryption). Protected by restrictive host permissions (`0700` directory / `0600` files on POSIX, restricted DACLs on Windows), excluded from server backups and settings exports, and unreachable from plugin file APIs.
- `<config_dir>/plugins/<plugin-id>/` — Private per-plugin file storage (`scope="private"` in the plugin file API).
- `<config_dir>/plugins/public/` — Shared plugin file storage (`scope="public"` or `scope="shared"` in the plugin file API).
- `<config_dir>/panorama.{jpeg,jpg,png,webp}` — Optional custom background panorama image served by `GET /api/panorama`.

On first access, BSM moves recognized legacy bootstrap, log, runtime, and private plugin data directories into their dedicated locations. Existing legacy SQLite databases remain in place, including their WAL/SHM files; explicit database URLs are always preserved. If both legacy and nested default databases exist without an explicit database URL, startup reports a conflict and preserves both files. Select the intended database with `db_url` or `BSM_DB_URL`. Relocate databases only while BSM is stopped, using a consistent SQLite backup.

### Data root (`<data_dir>`)

The `--data-dir` option (or `BSM_DATA_DIR`, defaulting to `<config_dir>/data`) holds server installations and user-managed assets:

- `<data_dir>/servers/<server_name>/` — Individual Bedrock server installations (and reserved `.bsm-*` staging/recovery journals). Each server's own `config/` subdirectory belongs to Minecraft script modules and is included in that server's backups.
- `<data_dir>/backups/<server_name>/` — Portable `.bsmbackup` archives, catalogs, and CLI database backups.
- `<data_dir>/content/worlds/` and `<data_dir>/content/addons/` — Uploaded or placed `.mcworld`, `.mcpack`, and `.mcaddon` packages.
- `<data_dir>/.downloads/` — Downloaded Bedrock installer archives (`stable/`, `preview/`, and user-placed archives in `custom/`).
- `<data_dir>/plugins/` — Installed Python plugin `.py` modules and package directories (`<plugin_name>/__init__.py`). Note that `<data_dir>/plugins/` holds **plugin code**, whereas `<config_dir>/plugins/` holds **plugin data files**. The directory names `public`, `shared`, and `private` are reserved by the plugin data system and cannot be used as plugin identifiers; symbolic links inside `<config_dir>/plugins/` and `<config_dir>/credentials/` are rejected.
- `<data_dir>/themes/` — Shared custom `.css` stylesheets exposed to the web interface.
