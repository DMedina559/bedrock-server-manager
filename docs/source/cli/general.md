# Command-line tools

BSM's local command manages the web host and its installation. The separate `bsm-cli` client performs server-management operations against the HTTP API.

## Local hosting and administration

```sh
bedrock-server-manager --help
bedrock-server-manager setup
bedrock-server-manager web start
bedrock-server-manager web stop --timeout 180
```

In addition to `web start` and `web stop`, the local `bedrock-server-manager` command provides administration and recovery tools that operate directly against your local configuration directory:

| Command | Purpose |
|---|---|
| `bedrock-server-manager setup` | Interactive initial setup for data directory, database URL, web bind host/port, and system service |
| `bedrock-server-manager web` | Start or stop the FastAPI web host (`start`, `stop`) |
| `bedrock-server-manager service` | Configure, enable, disable, remove, or check OS service status (`configure`, `enable`, `disable`, `remove`, `status`) |
| `bedrock-server-manager database` | Inspect schema status, run migrations, or back up and restore the database (`status`, `upgrade`, `downgrade`, `backup`, `restore`) |
| `bedrock-server-manager logs` | List, view, or follow application and server logs with verified PID status (`--app`, `--server`, `--list`, `--lines`, `--follow`) |
| `bedrock-server-manager cleanup` | Clean Python `__pycache__` bytecode (`--cache`), old `.log` files (`--logs`, `--log-dir`), or orphaned plugin/server/addon artifacts (`--orphans`, `--plugins`, `--servers`, `--addons`, `--all`, `--dry-run`) |
| `bedrock-server-manager backup` | Offline `.bsmbackup` archive inspection and extraction (`inspect`, `extract`) |
| `bedrock-server-manager reset-password` | Reset a local user account's password and revoke its existing sessions |
| `bedrock-server-manager reset-mfa` | Clear MFA, passkeys, and trusted devices for a locked-out local account |

Place global configuration options (`--config-dir`, `--data-dir`, `--db-url`, `--log-level`) before the subcommand. Keep the same configuration directory when starting, stopping or configuring a service. See the [local command reference](commands.rst) and [runtime guide](../extras/web_runtime.md).

## Remote management

Install the supported client with:

```sh
python -m pip install --upgrade 'bedrock-server-manager[cli]'
bsm-cli --help
```

Authenticate against a running BSM instance using a username and password, a long-lived integration token, or by minting an integration token during password login:

```sh
# Interactive or flag-based password login (defaults to http://127.0.0.1:11325)
bsm-cli auth login -u admin

# Mint and store a long-lived integration token during password login
bsm-cli auth login -u admin --long-lived --token-name "workstation-cli"

# Authenticate with an existing integration token (bsm_it_...) via flag or stdin
bsm-cli auth login --token bsm_it_...
echo "$BSM_TOKEN" | bsm-cli auth login --with-token --base-url https://bsm.example.com

# Check current authentication status and credential storage backend
bsm-cli auth status
```

`bsm-cli` stores bearer tokens and MFA trusted-device tokens in your operating system's credential store (`keyring`, Windows Credential Manager, macOS Keychain, or Linux `secret-tool`) when available, keeping secrets out of plaintext configuration files. You can also manage active sessions (`bsm-cli auth sessions`), trusted devices (`bsm-cli auth devices`), integration tokens (`bsm-cli auth tokens`), and security audit logs (`bsm-cli audit`) directly from the CLI.

Consult the [client command reference](api_client_commands.rst) for connection, authentication, scheduler, and server commands. Client compatibility follows the HTTP contract; update clients when upgrading across a contract-changing release.

## Interactive client

The interactive client groups monitoring, server management, application settings and content operations.

```{figure} ../../images/cli_menu.png
:alt: Interactive CLI overview listing servers and navigation destinations
:width: 600px
:align: center

The CLI overview lists managed servers and available destinations.
```

```{figure} ../../images/cli_manage_server_menu.png
:alt: Interactive CLI menu for managing a selected Bedrock server
:width: 600px
:align: center

A selected server has its own management menu.
```
