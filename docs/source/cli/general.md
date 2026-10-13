# Command-line tools

BSM's local command manages the web host and its installation. The separate `bsm-cli` client performs server-management operations against the HTTP API.

## Local hosting

```sh
bedrock-server-manager --help
bedrock-server-manager web start
bedrock-server-manager web stop --timeout 180
```

Place global configuration options before `web`. Keep the same configuration directory when starting, stopping or configuring a service. See the [local command reference](commands.rst) and [runtime guide](../extras/web_runtime.md).

## Remote management

Install the supported client with:

```sh
python -m pip install --upgrade 'bedrock-server-manager[cli]'
bsm-cli --help
```

Consult the [client command reference](api_client_commands.rst) for connection, authentication and server commands. Client compatibility follows the HTTP contract; update clients when upgrading across a contract-changing release.
